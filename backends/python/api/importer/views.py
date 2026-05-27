import csv
import logging
import os
import posixpath
import re
from datetime import timedelta
from io import StringIO, TextIOWrapper
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

import xlrd
from kombu.exceptions import OperationalError as KombuOperationalError

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from main.utils import AuthorizedRequest
from main.utils.decorators import auth_required, log_errors

from .models import ImportAliasRule, ImportSession, ImportTemplate, ImporterUserRole
from .services.b24_fields import (
    SMART_PROCESS_ENTITY_TYPE,
    build_linked_entities_payload,
    fetch_entity_fields,
    fetch_smart_process_types,
    normalize_smart_process_entity_config,
)
from .services.background_jobs import (
    enqueue_import_session_dry_run,
    enqueue_import_session_retry,
    enqueue_import_session_run,
    is_import_queue_enabled,
)
from .services.example_templates import (
    build_example_template_filename,
    build_example_template_xlsx,
    build_smart_process_example_template_filename,
    build_smart_process_example_template_xlsx,
)
from .services.error_messages import safe_format_import_error
from .services.excel_values import normalize_xlsx_cell_value, parse_xlsx_date_style_formats
from .services.import_execution import execute_dry_run, execute_import, normalize_entity_dedup_settings
from .services.mapping import (
    build_candidate_mapping_bundle,
    normalize_mapping_value,
    normalize_saved_mapping,
    resolve_field_item_value,
)
from .services.permissions import (
    can_cancel_session,
    can_edit_session,
    can_run_session,
    get_permissions,
    has_permission,
    is_portal_admin,
    normalize_assignable_role,
    resolve_role,
)
from .services.preflight import build_mapping_preflight
from .services.user_resolution import BitrixUserResolver, list_bitrix_users
from .services.validation import build_validation_result


XLSX_MAIN_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
XLSX_REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
CELL_REF_RE = re.compile(r"([A-Z]+)")

MAX_IMPORT_ROWS = 100_000
SAMPLE_PREVIEW_ROW_LIMIT = 30
DRY_RUN_MODE_SAMPLE_PREVIEW = "sample_preview"
DRY_RUN_MODE_PREIMPORT_SCAN = "preimport_scan"
IMPORT_MODE_SIMPLE = "simple"
IMPORT_MODE_ADVANCED = "advanced"

_ALLOWED_UPLOAD_EXTENSIONS = {".xlsx", ".xls", ".csv"}
_XLSX_MAGIC = b"PK\x03\x04"          # ZIP / OOXML
_XLS_MAGIC  = b"\xd0\xcf\x11\xe0"    # OLE2 Compound Document
_MAX_UPLOAD_FILENAME_LENGTH = 200


def get_max_import_file_size_bytes() -> int:
    return int(
        getattr(
            settings,
            "IMPORT_MAX_FILE_SIZE_BYTES",
            getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", 50 * 1024 * 1024),
        )
        or 50 * 1024 * 1024
    )


def get_max_import_file_size_megabytes() -> int:
    return max(1, get_max_import_file_size_bytes() // (1024 * 1024))


def build_import_row_limit_payload(total_rows: int) -> dict:
    normalized_total_rows = max(0, int(total_rows or 0))
    row_limit_exceeded = normalized_total_rows > MAX_IMPORT_ROWS
    row_limit_error = ""
    if row_limit_exceeded:
        row_limit_error = (
            f"Файл содержит слишком много строк данных ({normalized_total_rows:,}). "
            f"Максимум: {MAX_IMPORT_ROWS:,} строк за один импорт."
        )

    return {
        "total_rows": normalized_total_rows,
        "max_import_rows": MAX_IMPORT_ROWS,
        "row_limit_exceeded": row_limit_exceeded,
        "row_limit_error": row_limit_error,
    }


def build_import_row_limit_error_response(total_rows: int, *, status: int = 400):
    row_limit = build_import_row_limit_payload(total_rows)
    return JsonResponse(
        {
            "error": row_limit["row_limit_error"],
            "row_limit": row_limit,
        },
        status=status,
    )


def _validate_and_sanitize_upload(upload) -> str:
    """Validate file extension + magic bytes; return sanitized filename. Raises ValueError."""
    raw_name = str(upload.name or "").strip()
    safe_name = os.path.basename(raw_name.replace("\\", "/"))
    if not safe_name:
        raise ValueError("Имя файла не может быть пустым")
    if len(safe_name) > _MAX_UPLOAD_FILENAME_LENGTH:
        safe_name = safe_name[-_MAX_UPLOAD_FILENAME_LENGTH:]

    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in _ALLOWED_UPLOAD_EXTENSIONS:
        allowed = ", ".join(sorted(_ALLOWED_UPLOAD_EXTENSIONS))
        raise ValueError(f"Недопустимый формат файла '{ext}'. Разрешены: {allowed}")

    header = upload.read(4)
    upload.seek(0)
    if ext == ".xlsx" and not header.startswith(_XLSX_MAGIC):
        raise ValueError("Файл не является корректным XLSX (неверная сигнатура файла)")
    if ext == ".xls" and not header.startswith(_XLS_MAGIC):
        raise ValueError("Файл не является корректным XLS (неверная сигнатура файла)")

    return safe_name
IMPORT_RUN_FAILED_STATUSES = {"failed", "skipped"}
IMPORT_RUN_RETRYABLE_STATUSES = {"failed", "skipped", "cancelled"}
IMPORT_RUN_SKIPPED_STATUSES = {"skipped", "skipped_duplicate"}
IMPORT_ACTIVE_JOB_STATES = {"queued", "running"}
IMPORT_RUN_STATUS_LABELS = {
    "created": "Создано",
    "updated": "Обновлено",
    "failed": "Ошибка",
    "skipped": "Пропущено",
    "skipped_duplicate": "Дубль пропущен",
    "pending_decision": "Ожидает решения",
    "cancelled": "Остановлено",
}


def normalize_dry_run_mode(value: object) -> str:
    normalized_value = str(value or "").strip().lower()
    if normalized_value == DRY_RUN_MODE_SAMPLE_PREVIEW:
        return DRY_RUN_MODE_SAMPLE_PREVIEW
    return DRY_RUN_MODE_PREIMPORT_SCAN


def normalize_import_mode(value: object) -> str:
    return IMPORT_MODE_SIMPLE if str(value or "").strip().lower() == IMPORT_MODE_SIMPLE else IMPORT_MODE_ADVANCED


def is_simple_import_mode(value: object) -> bool:
    return normalize_import_mode(value) == IMPORT_MODE_SIMPLE


def resolve_import_mode_marker(value: object) -> str:
    normalized_value = str(value or "").strip().lower()
    if normalized_value in {IMPORT_MODE_SIMPLE, IMPORT_MODE_ADVANCED}:
        return normalized_value
    return ""


def resolve_session_mode_settings(import_settings: object, import_mode: object) -> tuple[str, dict, dict, dict]:
    safe_import_settings = import_settings if isinstance(import_settings, dict) else {}
    normalized_import_mode = normalize_import_mode(import_mode)
    stored_import_mode = resolve_import_mode_marker(safe_import_settings.get("import_mode"))

    def _resolve_setting(setting_key: str) -> dict:
        scoped_settings = safe_import_settings.get(f"{setting_key}_by_mode")
        if isinstance(scoped_settings, dict):
            scoped_value = scoped_settings.get(normalized_import_mode)
            if isinstance(scoped_value, dict):
                return scoped_value

        legacy_value = safe_import_settings.get(setting_key, {})
        if not isinstance(legacy_value, dict):
            legacy_value = {}

        if normalized_import_mode == IMPORT_MODE_SIMPLE:
            return legacy_value if stored_import_mode == IMPORT_MODE_SIMPLE else {}

        return legacy_value

    return (
        normalized_import_mode,
        _resolve_setting("mapping"),
        _resolve_setting("dedup"),
        _resolve_setting("task_defaults"),
    )


def build_mode_scoped_import_settings(
    import_settings: object,
    *,
    import_mode: object,
    mapping: dict,
    dedup: dict,
    task_defaults: dict,
) -> dict:
    safe_import_settings = import_settings if isinstance(import_settings, dict) else {}
    normalized_import_mode = normalize_import_mode(import_mode)

    def _merge_mode_bucket(setting_key: str, setting_value: dict) -> dict:
        existing_bucket = safe_import_settings.get(f"{setting_key}_by_mode")
        safe_bucket = existing_bucket if isinstance(existing_bucket, dict) else {}
        return {
            **safe_bucket,
            normalized_import_mode: setting_value,
        }

    return {
        **safe_import_settings,
        "import_mode": normalized_import_mode,
        "mapping": mapping,
        "dedup": dedup,
        "task_defaults": task_defaults,
        "mapping_by_mode": _merge_mode_bucket("mapping", mapping),
        "dedup_by_mode": _merge_mode_bucket("dedup", dedup),
        "task_defaults_by_mode": _merge_mode_bucket("task_defaults", task_defaults),
    }


def get_dry_run_summary_key(mode: str) -> str:
    return "sample_preview" if mode == DRY_RUN_MODE_SAMPLE_PREVIEW else "preimport_scan"


def resolve_dry_run_dedup_settings(entity_type: str, dedup_settings: object, *, mode: str) -> dict:
    normalized_dedup_settings = normalize_entity_dedup_settings(entity_type, dedup_settings)
    if normalize_dry_run_mode(mode) == DRY_RUN_MODE_SAMPLE_PREVIEW:
        return {
            **normalized_dedup_settings,
            "strategy": "create",
            "fields": [],
        }
    return normalized_dedup_settings


def serialize_session(session: ImportSession) -> dict:
    import_settings = session.import_settings if isinstance(session.import_settings, dict) else {}
    return {
        "id": str(session.id),
        "entity_type": session.entity_type,
        "entity_config": import_settings.get("entity_config") if isinstance(import_settings.get("entity_config"), dict) else None,
        "source_format": session.source_format,
        "status": session.status,
        "original_filename": session.original_filename,
        "stored_file_name": session.stored_file.name,
        "file_size_bytes": session.file_size_bytes,
        "source_sheet_name": session.source_sheet_name,
        "preview_data": session.preview_data,
        "portal_member_id": session.portal_member_id,
        "portal_domain": session.portal_domain,
        "processed_rows": session.processed_rows,
        "successful_rows": session.successful_rows,
        "failed_rows": session.failed_rows,
        "total_rows": session.total_rows,
        "summary": session.summary,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


def serialize_session_history_summary(summary: dict | None) -> dict:
    if not isinstance(summary, dict):
        return {}

    payload = {}
    import_run = summary.get("import_run")
    if isinstance(import_run, dict):
        counters = {}
        for key in (
            "checked_rows",
            "created_rows",
            "updated_rows",
            "skipped_rows",
            "failed_rows",
            "cancelled_rows",
            "remaining_rows",
            "retried_rows",
        ):
            value = import_run.get(key)
            if value is None:
                continue
            try:
                counters[key] = int(value)
            except (TypeError, ValueError):
                continue
        if counters:
            payload["import_run"] = counters

    job = summary.get("job")
    if isinstance(job, dict):
        state = str(job.get("state") or "").strip()
        if state:
            payload["job"] = {"state": state}

    return payload


def serialize_session_history_item(session: ImportSession) -> dict:
    import_settings = session.import_settings if isinstance(session.import_settings, dict) else {}
    return {
        "id": str(session.id),
        "entity_type": session.entity_type,
        "entity_config": import_settings.get("entity_config") if isinstance(import_settings.get("entity_config"), dict) else None,
        "source_format": session.source_format,
        "status": session.status,
        "original_filename": session.original_filename,
        "processed_rows": session.processed_rows,
        "successful_rows": session.successful_rows,
        "failed_rows": session.failed_rows,
        "total_rows": session.total_rows,
        "summary": serialize_session_history_summary(session.summary),
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


def serialize_template(template: ImportTemplate) -> dict:
    return {
        "id": str(template.id),
        "entity_type": template.entity_type,
        "entity_config": template.entity_config if isinstance(template.entity_config, dict) and template.entity_config else None,
        "name": template.name,
        "mapping_schema": template.mapping_schema,
        "column_settings": template.column_settings,
        "dedup_settings": template.dedup_settings,
        "is_active": template.is_active,
        "created_at": template.created_at.isoformat(),
        "updated_at": template.updated_at.isoformat(),
    }


def serialize_alias_rule(alias_rule: ImportAliasRule, field_titles: dict[str, str] | None = None) -> dict:
    field_title_map = field_titles if isinstance(field_titles, dict) else {}
    target_field_id = str(alias_rule.target_field_id or "")
    return {
        "id": str(alias_rule.id),
        "source_label": str(alias_rule.source_label or ""),
        "target_field_id": target_field_id,
        "target_field_title": str(field_title_map.get(target_field_id) or target_field_id),
    }


def normalize_task_defaults(payload, account=None) -> dict:
    if not isinstance(payload, dict):
        return {}

    raw_default_responsible_id = payload.get("default_responsible_id")
    raw_default_creator_id = payload.get("default_creator_id")
    raw_default_comment_author_id = payload.get("default_comment_author_id")
    if raw_default_responsible_id is None and isinstance(payload.get("task_defaults"), dict):
        raw_default_responsible_id = payload.get("task_defaults", {}).get("default_responsible_id")
    if raw_default_creator_id is None and isinstance(payload.get("task_defaults"), dict):
        raw_default_creator_id = payload.get("task_defaults", {}).get("default_creator_id")
    if raw_default_comment_author_id is None and isinstance(payload.get("task_defaults"), dict):
        raw_default_comment_author_id = payload.get("task_defaults", {}).get("default_comment_author_id")

    normalized_default_responsible_id = str(raw_default_responsible_id or "").strip()
    normalized_default_creator_id = str(raw_default_creator_id or "").strip()
    normalized_default_comment_author_id = str(raw_default_comment_author_id or "").strip()
    if not normalized_default_responsible_id and not normalized_default_creator_id and not normalized_default_comment_author_id:
        return {}

    if account is not None and normalized_default_responsible_id:
        resolved_default_responsible_id = BitrixUserResolver(account).resolve(normalized_default_responsible_id)
        if resolved_default_responsible_id is None:
            raise ValueError("Default responsible user must be a valid Bitrix user")
        normalized_default_responsible_id = str(resolved_default_responsible_id)

    if account is not None and normalized_default_creator_id:
        resolved_default_creator_id = BitrixUserResolver(account).resolve(normalized_default_creator_id)
        if resolved_default_creator_id is None:
            raise ValueError("Default creator user must be a valid Bitrix user")
        normalized_default_creator_id = str(resolved_default_creator_id)

    if account is not None and normalized_default_comment_author_id:
        resolved_default_comment_author_id = BitrixUserResolver(account).resolve(normalized_default_comment_author_id)
        if resolved_default_comment_author_id is None:
            raise ValueError("Default comment author must be a valid Bitrix user")
        normalized_default_comment_author_id = str(resolved_default_comment_author_id)

    task_defaults = {}
    if normalized_default_responsible_id:
        task_defaults["default_responsible_id"] = normalized_default_responsible_id
    if normalized_default_creator_id:
        task_defaults["default_creator_id"] = normalized_default_creator_id
    if normalized_default_comment_author_id:
        task_defaults["default_comment_author_id"] = normalized_default_comment_author_id
    return task_defaults


def build_task_default_field_values(entity_type: str, task_defaults: dict | None) -> dict:
    if not isinstance(task_defaults, dict):
        return {}

    if entity_type == ImportSession.EntityType.TASK:
        default_responsible_id = str(task_defaults.get("default_responsible_id") or "").strip()
        default_creator_id = str(task_defaults.get("default_creator_id") or "").strip()
        default_field_values = {}
        if default_responsible_id:
            default_field_values["RESPONSIBLE_ID"] = default_responsible_id
        if default_creator_id:
            default_field_values["CREATED_BY"] = default_creator_id
        return default_field_values

    if entity_type == ImportSession.EntityType.TASK_COMMENT:
        default_comment_author_id = str(task_defaults.get("default_comment_author_id") or "").strip()
        if not default_comment_author_id:
            return {}

        return {
            "AUTHOR_ID": default_comment_author_id,
        }

    return {}


def serialize_user_role(role: ImporterUserRole) -> dict:
    return {
        "id": str(role.id),
        "b24_user_id": role.b24_user_id,
        "role": role.role,
        "granted_by_b24_user_id": role.granted_by_b24_user_id,
        "created_at": role.created_at.isoformat(),
        "updated_at": role.updated_at.isoformat(),
    }


def build_permissions_payload(account) -> dict:
    role = resolve_role(account)
    return {
        "role": role,
        "permissions": get_permissions(role),
        "user_id": int(getattr(account, "b24_user_id", 0) or 0),
        "is_portal_admin": is_portal_admin(account),
    }


def permission_denied_response():
    return JsonResponse({"error": "Permission denied"}, status=403)


def build_import_report_filename(original_filename: str) -> str:
    normalized_filename = str(original_filename or "").strip() or "import"
    base_name = normalized_filename.rsplit(".", 1)[0]
    sanitized_name = re.sub(r"[^A-Za-z0-9._-]+", "-", base_name).strip("-") or "import"
    return f"{sanitized_name}-report.csv"


@xframe_options_exempt
@require_GET
@log_errors("import_example_template_xlsx")
@auth_required
def import_example_template_xlsx(request: AuthorizedRequest):
    account = request.bitrix24_account
    if not has_permission(account, "sessions.create"):
        return permission_denied_response()

    entity_type = str(request.GET.get("entity_type") or "").strip()
    try:
        if entity_type == SMART_PROCESS_ENTITY_TYPE:
            entity_config = normalize_session_entity_config(entity_type, request.GET)
            fields = fetch_entity_fields(account, entity_type, entity_config=entity_config)
            template_content = build_smart_process_example_template_xlsx(entity_config, fields)
            filename = build_smart_process_example_template_filename(entity_config)
        else:
            template_content = build_example_template_xlsx(entity_type)
            filename = build_example_template_filename(entity_type)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    response = HttpResponse(
        template_content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def build_import_result_summary(results: list[dict], checked_rows: int | None = None) -> dict:
    created_ids = []
    updated_ids = []
    created_rows = 0
    updated_rows = 0
    failed_rows = 0
    skipped_rows = 0
    cancelled_rows = 0
    derived_checked_rows = 0

    for item in results:
        if not isinstance(item, dict):
            continue

        status = str(item.get("status") or "").strip()
        record_id = item.get("record_id")

        if status != "cancelled":
            derived_checked_rows += 1

        if status == "created":
            created_rows += 1
            if record_id is not None and record_id != "":
                created_ids.append(record_id)
        elif status == "updated":
            updated_rows += 1
            if record_id is not None and record_id != "":
                updated_ids.append(record_id)
        elif status == "cancelled":
            cancelled_rows += 1

        if status in IMPORT_RUN_FAILED_STATUSES:
            failed_rows += 1

        if status in IMPORT_RUN_SKIPPED_STATUSES:
            skipped_rows += 1

    return {
        "checked_rows": int(checked_rows if checked_rows is not None else derived_checked_rows),
        "created_rows": created_rows,
        "updated_rows": updated_rows,
        "failed_rows": failed_rows,
        "skipped_rows": skipped_rows,
        "cancelled": cancelled_rows > 0,
        "cancelled_rows": cancelled_rows,
        "remaining_rows": cancelled_rows,
        "created_ids": created_ids,
        "updated_ids": updated_ids,
        "results": results,
    }


def collect_retryable_row_numbers(results: list[dict]) -> list[int]:
    row_numbers = []
    seen_row_numbers = set()

    for item in results:
        if not isinstance(item, dict):
            continue

        status = str(item.get("status") or "").strip()
        if status not in IMPORT_RUN_RETRYABLE_STATUSES:
            continue

        try:
            row_number = int(item.get("row_number"))
        except (TypeError, ValueError):
            continue

        if row_number in seen_row_numbers:
            continue

        seen_row_numbers.add(row_number)
        row_numbers.append(row_number)

    return sorted(row_numbers)


def filter_rows_by_row_numbers(rows: list[list], row_numbers: list[int], allowed_row_numbers: list[int]) -> tuple[list[list], list[int]]:
    allowed_row_numbers_set = set(allowed_row_numbers)
    filtered_rows = []
    filtered_row_numbers = []

    for index, row_number in enumerate(row_numbers):
        if row_number not in allowed_row_numbers_set:
            continue
        if index >= len(rows):
            continue

        filtered_rows.append(rows[index])
        filtered_row_numbers.append(row_number)

    return filtered_rows, filtered_row_numbers


def merge_import_run_results(previous_import_run: dict, retry_result: dict) -> dict:
    previous_results = previous_import_run.get("results") if isinstance(previous_import_run, dict) else []
    retry_results = retry_result.get("results") if isinstance(retry_result, dict) else []
    retry_results_by_row_number = {}

    for item in retry_results if isinstance(retry_results, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            row_number = int(item.get("row_number"))
        except (TypeError, ValueError):
            continue
        retry_results_by_row_number[row_number] = item

    merged_results = []
    seen_retry_rows = set()

    for item in previous_results if isinstance(previous_results, list) else []:
        if not isinstance(item, dict):
            continue

        try:
            row_number = int(item.get("row_number"))
        except (TypeError, ValueError):
            merged_results.append(item)
            continue

        if row_number in retry_results_by_row_number:
            merged_results.append(retry_results_by_row_number[row_number])
            seen_retry_rows.add(row_number)
        else:
            merged_results.append(item)

    for row_number, item in sorted(retry_results_by_row_number.items()):
        if row_number in seen_retry_rows:
            continue
        merged_results.append(item)

    merged_summary = build_import_result_summary(merged_results)
    merged_summary["auth_error"] = str(retry_result.get("auth_error") or "")
    merged_summary["fatal_error"] = str(retry_result.get("fatal_error") or "")
    return merged_summary


def normalize_per_row_decisions(raw: object) -> dict:
    if not isinstance(raw, dict):
        return {}

    def _normalize_decision_value(value: object) -> str:
        normalized_value = str(value or "").strip().lower()
        return normalized_value if normalized_value in ("create", "update", "skip") else ""

    result = {}
    for row_num, decision in raw.items():
        normalized_row_number = str(row_num)
        normalized_decision = _normalize_decision_value(decision)
        if normalized_decision:
            result[normalized_row_number] = normalized_decision
            continue

        if not isinstance(decision, dict):
            continue

        entity_decisions = {}
        for entity_id, entity_decision in decision.items():
            normalized_entity_decision = _normalize_decision_value(entity_decision)
            normalized_entity_id = str(entity_id or "").strip().lower()
            if normalized_entity_id and normalized_entity_decision:
                entity_decisions[normalized_entity_id] = normalized_entity_decision

        if entity_decisions:
            result[normalized_row_number] = entity_decisions
    return result


def collect_pending_decision_requirements(dedup_settings: object, summary: object) -> dict[int, list[str]]:
    if not isinstance(summary, dict):
        return {}

    results = summary.get("results")
    if not isinstance(results, list):
        return {}

    normalized_dedup_settings = dedup_settings if isinstance(dedup_settings, dict) else {}
    pending_requirements = {}

    for item in results:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "").strip() != "pending_decision":
            continue
        try:
            row_number = int(item.get("row_number"))
        except (TypeError, ValueError):
            continue

        linked_summary = item.get("linked") if isinstance(item.get("linked"), dict) else {}
        linked_entity_requirements = [
            entity_id
            for entity_id, entity_settings in normalized_dedup_settings.items()
            if isinstance(entity_settings, dict)
            and str(entity_settings.get("strategy") or "").strip().lower() == "ask"
            and isinstance(linked_summary.get(entity_id), dict)
            and (
                linked_summary[entity_id].get("record_id") is not None
                or bool(linked_summary[entity_id].get("duplicate_match_fields"))
            )
        ]

        pending_requirements[row_number] = linked_entity_requirements

    return pending_requirements


def collect_pending_decision_row_numbers(dry_run_summary: object) -> list[int]:
    if not isinstance(dry_run_summary, dict):
        return []

    row_numbers = []
    seen_row_numbers = set()
    for item in dry_run_summary.get("results", []) if isinstance(dry_run_summary.get("results"), list) else []:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "").strip() != "pending_decision":
            continue
        try:
            row_number = int(item.get("row_number"))
        except (TypeError, ValueError):
            continue
        if row_number in seen_row_numbers:
            continue
        seen_row_numbers.add(row_number)
        row_numbers.append(row_number)

    return sorted(row_numbers)


def dedup_settings_require_pending_decisions(dedup_settings: object) -> bool:
    if not isinstance(dedup_settings, dict):
        return False

    if str(dedup_settings.get("strategy") or "").strip().lower() == "ask":
        return True

    return any(dedup_settings_require_pending_decisions(value) for value in dedup_settings.values())


def get_missing_pending_decision_rows(dedup_settings: object, summary: object, per_row_decisions: object) -> list[int] | None:
    if not dedup_settings_require_pending_decisions(dedup_settings):
        return []

    if not isinstance(summary, dict):
        return None

    preimport_scan_summary = summary.get("preimport_scan")
    if not isinstance(preimport_scan_summary, dict):
        dry_run_summary = summary.get("dry_run")
        if not isinstance(dry_run_summary, dict):
            return None
        dry_run_mode = normalize_dry_run_mode(dry_run_summary.get("mode"))
        if dry_run_mode == DRY_RUN_MODE_SAMPLE_PREVIEW:
            return None
        preimport_scan_summary = dry_run_summary

    normalized_decisions = normalize_per_row_decisions(per_row_decisions)
    pending_requirements = collect_pending_decision_requirements(dedup_settings, preimport_scan_summary)
    if pending_requirements:
        missing_rows = []
        for row_number, linked_entity_requirements in pending_requirements.items():
            row_decision = normalized_decisions.get(str(row_number))
            if isinstance(row_decision, str) and row_decision:
                continue

            if linked_entity_requirements:
                if not isinstance(row_decision, dict):
                    missing_rows.append(row_number)
                    continue

                if any(
                    str(row_decision.get(entity_id) or "").strip().lower() not in ("create", "update", "skip")
                    for entity_id in linked_entity_requirements
                ):
                    missing_rows.append(row_number)
                continue

            if str(row_number) not in normalized_decisions:
                missing_rows.append(row_number)

        return missing_rows

    pending_row_numbers = collect_pending_decision_row_numbers(preimport_scan_summary)
    return [row_number for row_number in pending_row_numbers if str(row_number) not in normalized_decisions]


def build_import_phase_items(
    *,
    create_phase_total: int,
    duplicate_phase_total: int,
    create_phase_processed: int,
    duplicate_phase_processed: int,
    active_phase: str,
) -> list[dict]:
    normalized_active_phase = str(active_phase or "").strip()
    phase_items = [
        {
            "id": "new_records",
            "label": "Импорт новых записей",
            "total_rows": max(0, int(create_phase_total or 0)),
            "processed_rows": max(0, min(int(create_phase_processed or 0), max(0, int(create_phase_total or 0)))),
        },
        {
            "id": "duplicates",
            "label": "Обработка дублей",
            "total_rows": max(0, int(duplicate_phase_total or 0)),
            "processed_rows": max(0, min(int(duplicate_phase_processed or 0), max(0, int(duplicate_phase_total or 0)))),
        },
    ]
    any_active = False
    for index, item in enumerate(phase_items):
        if item["total_rows"] <= 0:
            item["status"] = "skipped"
            continue
        if item["processed_rows"] >= item["total_rows"]:
            item["status"] = "completed"
            continue
        if not any_active and normalized_active_phase == item["id"]:
            item["status"] = "current"
            any_active = True
            continue
        if not any_active and normalized_active_phase not in {"new_records", "duplicates"} and index == 0:
            item["status"] = "current"
            any_active = True
            continue
        item["status"] = "upcoming"

    if not any_active:
        for item in phase_items:
            if item.get("status") == "upcoming":
                item["status"] = "current"
                any_active = True
                break

    return phase_items


def summarize_import_phase_progress(
    *,
    create_phase_total: int,
    duplicate_phase_total: int,
    create_phase_processed: int,
    duplicate_phase_processed: int,
    active_phase: str,
) -> dict:
    phase_items = build_import_phase_items(
        create_phase_total=create_phase_total,
        duplicate_phase_total=duplicate_phase_total,
        create_phase_processed=create_phase_processed,
        duplicate_phase_processed=duplicate_phase_processed,
        active_phase=active_phase,
    )
    total_rows = sum(int(item.get("total_rows") or 0) for item in phase_items)
    processed_rows = sum(int(item.get("processed_rows") or 0) for item in phase_items)
    current_phase = next((item for item in phase_items if item.get("status") == "current"), None)
    completed = total_rows > 0 and processed_rows >= total_rows
    current_phase = current_phase or {}

    return {
        "phase": "completed" if completed else str(current_phase.get("id") or active_phase or "").strip(),
        "phase_label": "Импорт завершён" if completed else str(current_phase.get("label") or "").strip(),
        "total_rows": total_rows,
        "processed_rows": processed_rows,
        "phases": phase_items,
    }


def collect_preimport_scan_stage_row_numbers(preimport_scan_summary: object) -> tuple[list[int], list[int]]:
    if not isinstance(preimport_scan_summary, dict):
        return [], []

    create_phase_row_numbers = []
    duplicate_phase_row_numbers = []
    seen_create_rows = set()
    seen_duplicate_rows = set()

    for item in preimport_scan_summary.get("results", []) if isinstance(preimport_scan_summary.get("results"), list) else []:
        if not isinstance(item, dict):
            continue
        try:
            row_number = int(item.get("row_number"))
        except (TypeError, ValueError):
            continue

        status = str(item.get("status") or "").strip()
        if status in {"ready_update", "pending_decision", "skipped_duplicate"}:
            if row_number not in seen_duplicate_rows:
                seen_duplicate_rows.add(row_number)
                duplicate_phase_row_numbers.append(row_number)
            continue

        if row_number not in seen_create_rows:
            seen_create_rows.add(row_number)
            create_phase_row_numbers.append(row_number)

    return sorted(create_phase_row_numbers), sorted(duplicate_phase_row_numbers)


def merge_import_execution_results(*results: dict) -> dict:
    merged_results = []
    for result in results:
        if not isinstance(result, dict):
            continue
        if isinstance(result.get("results"), list):
            merged_results.extend(result["results"])

    merged_results.sort(key=lambda item: (int(item.get("row_number") or 0), str(item.get("status") or "")))
    return build_import_result_summary(merged_results)


def store_import_phase_progress(
    session: ImportSession,
    *,
    create_phase_total: int,
    duplicate_phase_total: int,
    create_phase_processed: int,
    duplicate_phase_processed: int,
    active_phase: str,
) -> None:
    summary = session.summary if isinstance(session.summary, dict) else {}
    summary = {
        **summary,
        "import_progress": summarize_import_phase_progress(
            create_phase_total=create_phase_total,
            duplicate_phase_total=duplicate_phase_total,
            create_phase_processed=create_phase_processed,
            duplicate_phase_processed=duplicate_phase_processed,
            active_phase=active_phase,
        ),
    }
    session.summary = summary


def get_preimport_scan_summary(summary: object) -> dict | None:
    if not isinstance(summary, dict):
        return None

    preimport_scan_summary = summary.get("preimport_scan")
    if isinstance(preimport_scan_summary, dict):
        return preimport_scan_summary

    dry_run_summary = summary.get("dry_run")
    if not isinstance(dry_run_summary, dict):
        return None

    if normalize_dry_run_mode(dry_run_summary.get("mode")) == DRY_RUN_MODE_SAMPLE_PREVIEW:
        return None

    return dry_run_summary


def is_session_cancel_requested(session_id) -> bool:
    return ImportSession.objects.filter(
        id=session_id,
        status=ImportSession.Status.CANCELLED,
    ).exists()


def build_import_report_csv(import_run: dict) -> str:
    csv_buffer = StringIO()
    csv_writer = csv.writer(csv_buffer, delimiter=";")
    csv_writer.writerow(
        [
            "Строка",
            "Статус",
            "Дата и время",
            "Сущность",
            "Название",
            "ID в Bitrix24",
            "Обновлённые поля",
            "Ошибка",
        ]
    )

    for item in import_run.get("results", []) if isinstance(import_run, dict) else []:
        if not isinstance(item, dict):
            continue

        status = str(item.get("status") or "").strip()
        updated_fields = item.get("updated_fields")
        updated_fields_str = ", ".join(updated_fields) if isinstance(updated_fields, list) else ""
        report_record_id = str(item.get("report_record_id") or "").strip()
        raw_record_id = item.get("record_id")
        record_id = report_record_id or ("" if raw_record_id in (None, "") else str(raw_record_id))
        csv_writer.writerow(
            [
                item.get("row_number", ""),
                IMPORT_RUN_STATUS_LABELS.get(status, status),
                str(item.get("report_date_time") or "").strip(),
                str(item.get("report_entity") or "").strip(),
                str(item.get("report_title") or "").strip(),
                record_id,
                updated_fields_str,
                str(item.get("error") or "").strip(),
            ]
        )

    return "\ufeff" + csv_buffer.getvalue()


def load_portal_session(portal_member_id: str, portal_domain: str, session_id):
    try:
        return ImportSession.objects.get(
            id=session_id,
            portal_member_id=portal_member_id,
            portal_domain=portal_domain,
        )
    except ImportSession.DoesNotExist:
        return None


def serialize_session_response_item(session: ImportSession) -> dict:
    return {
        "session_id": str(session.id),
        **serialize_session(session),
    }


def has_active_import_job(session: ImportSession) -> bool:
    if session.status == ImportSession.Status.RUNNING:
        return True

    summary = session.summary if isinstance(session.summary, dict) else {}
    job = summary.get("job") if isinstance(summary.get("job"), dict) else {}
    job_state = str(job.get("state") or "").strip().lower()
    return job_state in IMPORT_ACTIVE_JOB_STATES


def build_template_entity_scope(entity_type: str, entity_config: dict | None = None) -> str:
    if entity_type == SMART_PROCESS_ENTITY_TYPE:
        normalized_config = normalize_smart_process_entity_config(entity_config or {})
        return f"smart_process:{normalized_config['entityTypeId']}"
    return ""


def build_template_entity_config(entity_type: str, entity_config: dict | None = None) -> dict:
    if entity_type == SMART_PROCESS_ENTITY_TYPE:
        return normalize_smart_process_entity_config(entity_config or {})
    return {}


def load_portal_template(
    portal_member_id: str,
    portal_domain: str,
    template_id,
    entity_type: str | None = None,
    entity_scope_key: str | None = None,
):
    filters = {
        "id": template_id,
        "portal_member_id": portal_member_id,
        "portal_domain": portal_domain,
        "is_active": True,
    }
    if entity_type:
        filters["entity_type"] = entity_type
    if entity_scope_key is not None:
        filters["entity_scope_key"] = entity_scope_key

    try:
        return ImportTemplate.objects.get(**filters)
    except ImportTemplate.DoesNotExist:
        return None


def load_portal_alias_rules(
    portal_member_id: str,
    portal_domain: str,
    *,
    entity_type: str,
    entity_scope_key: str = "",
):
    return list(
        ImportAliasRule.objects.filter(
            portal_member_id=portal_member_id,
            portal_domain=portal_domain,
            entity_type=entity_type,
            entity_scope_key=entity_scope_key,
            is_active=True,
        ).order_by("source_label", "target_field_id")
    )


def can_view_session(account, session: ImportSession) -> bool:
    return has_permission(account, "sessions.view")


def column_index_to_letter(index: int) -> str:
    result = ""
    current = index
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        result = chr(65 + remainder) + result
    return result


def column_letter_to_index(column_letters: str) -> int:
    result = 0
    for letter in column_letters:
        result = result * 26 + (ord(letter) - 64)
    return result


def extract_cell_column_index(cell_reference: str) -> int:
    match = CELL_REF_RE.match(cell_reference or "")
    if not match:
        return 0
    return column_letter_to_index(match.group(1))


def read_xlsx_archive(session: ImportSession):
    if not session.stored_file:
        raise ValueError("Uploaded file is required")

    try:
        with session.stored_file.open("rb") as stored_file:
            with ZipFile(stored_file) as archive:
                workbook_xml = archive.read("xl/workbook.xml")
                workbook_rels_xml = archive.read("xl/_rels/workbook.xml.rels")
                shared_strings_xml = archive.read("xl/sharedStrings.xml") if "xl/sharedStrings.xml" in archive.namelist() else None
                styles_xml = archive.read("xl/styles.xml") if "xl/styles.xml" in archive.namelist() else None
                worksheet_files = {
                    file_name: archive.read(file_name)
                    for file_name in archive.namelist()
                    if file_name.startswith("xl/worksheets/")
                }
    except (BadZipFile, KeyError, FileNotFoundError, OSError) as error:
        raise ValueError("Unable to read workbook preview") from error

    try:
        workbook_root = ElementTree.fromstring(workbook_xml)
        workbook_rels_root = ElementTree.fromstring(workbook_rels_xml)
    except ElementTree.ParseError as error:
        raise ValueError("Unable to read workbook preview") from error

    relationships = {
        relation.attrib.get("Id"): relation.attrib.get("Target", "")
        for relation in workbook_rels_root.findall("rel:Relationship", XLSX_REL_NS)
        if relation.attrib.get("Id")
    }

    sheets = []
    for sheet in workbook_root.findall("main:sheets/main:sheet", XLSX_MAIN_NS):
        sheet_name = sheet.attrib.get("name")
        relation_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = relationships.get(relation_id, "")
        if sheet_name and target:
            sheets.append(
                {
                    "name": sheet_name,
                    "path": normalize_xlsx_part_path(target),
                }
            )

    if not sheets:
        raise ValueError("Workbook does not contain sheets")

    return sheets, worksheet_files, shared_strings_xml, styles_xml


def normalize_xlsx_part_path(target: str) -> str:
    normalized_target = str(target or "").replace("\\", "/").strip()
    if not normalized_target:
        return ""

    normalized_target = normalized_target.lstrip("/")
    if normalized_target.startswith("xl/"):
        return posixpath.normpath(normalized_target)
    return posixpath.normpath(posixpath.join("xl", normalized_target))


def parse_shared_strings(shared_strings_xml: bytes | None) -> list[str]:
    if not shared_strings_xml:
        return []

    try:
        root = ElementTree.fromstring(shared_strings_xml)
    except ElementTree.ParseError as error:
        raise ValueError("Unable to read workbook preview") from error

    shared_strings = []
    for string_item in root.findall("main:si", XLSX_MAIN_NS):
        text_parts = [
            text_node.text or ""
            for text_node in string_item.findall(".//main:t", XLSX_MAIN_NS)
        ]
        shared_strings.append("".join(text_parts))

    return shared_strings


def extract_sheet_names(session: ImportSession):
    if session.source_format == ImportSession.SourceFormat.CSV:
        return ["CSV"]

    if session.source_format == ImportSession.SourceFormat.XLS:
        if not session.stored_file:
            raise ValueError("Uploaded file is required")
        try:
            with session.stored_file.open("rb") as stored_file:
                workbook = xlrd.open_workbook(file_contents=stored_file.read())
            return workbook.sheet_names() or []
        except Exception as error:
            raise ValueError("Unable to read XLS workbook") from error

    if session.source_format != ImportSession.SourceFormat.XLSX:
        raise ValueError("Unsupported source format")

    sheets, _worksheet_files, _shared_strings_xml, _styles_xml = read_xlsx_archive(session)
    sheet_names = [sheet["name"] for sheet in sheets]
    if not sheet_names:
        raise ValueError("Workbook does not contain sheets")

    return sheet_names


def extract_rows_from_xlsx_sheet(
    sheet_xml: bytes,
    shared_strings: list[str] | None = None,
    date_style_formats: dict[int, str] | None = None,
    preview_limit: int | None = 20,
):
    try:
        root = ElementTree.fromstring(sheet_xml)
    except ElementTree.ParseError as error:
        raise ValueError("Unable to read workbook preview") from error

    rows = []
    row_numbers = []
    max_column_index = 0
    for row in root.findall("main:sheetData/main:row", XLSX_MAIN_NS):
        values_by_column = {}
        for cell in row.findall("main:c", XLSX_MAIN_NS):
            column_index = extract_cell_column_index(cell.attrib.get("r", ""))
            if column_index <= 0:
                continue

            cell_type = str(cell.attrib.get("t") or "")
            try:
                style_index = int(cell.attrib.get("s")) if cell.attrib.get("s") is not None else None
            except (TypeError, ValueError):
                style_index = None

            inline_string = cell.find("main:is/main:t", XLSX_MAIN_NS)
            if inline_string is not None and inline_string.text is not None:
                value = inline_string.text
            else:
                value_node = cell.find("main:v", XLSX_MAIN_NS)
                value = value_node.text if value_node is not None and value_node.text is not None else ""
                if cell_type == "s":
                    try:
                        value = (shared_strings or [])[int(value)]
                    except (IndexError, TypeError, ValueError):
                        value = ""
                else:
                    value = normalize_xlsx_cell_value(
                        value,
                        cell_type=cell_type,
                        style_format=(date_style_formats or {}).get(style_index or -1, ""),
                    )

            values_by_column[column_index] = value
            max_column_index = max(max_column_index, column_index)

        if not values_by_column:
            continue

        row_values = [
            values_by_column.get(column_index, "")
            for column_index in range(1, max_column_index + 1)
        ]
        rows.append(row_values)
        row_numbers.append(int(row.attrib.get("r", len(row_numbers) + 1)))
        if preview_limit is not None and len(rows) >= preview_limit:
            break

    columns = [column_index_to_letter(index) for index in range(1, max_column_index + 1)]
    return columns, rows, row_numbers


def extract_rows_from_xls(session: ImportSession, sheet_name: str, preview_limit: int | None = 20):
    try:
        with session.stored_file.open("rb") as stored_file:
            workbook = xlrd.open_workbook(file_contents=stored_file.read())
    except Exception as error:
        raise ValueError("Unable to read XLS workbook") from error

    try:
        sheet = workbook.sheet_by_name(sheet_name)
    except xlrd.XLRDError:
        raise ValueError("Selected sheet does not exist")

    rows = []
    row_numbers = []
    max_columns = 0
    for row_index in range(sheet.nrows):
        row_values = []
        for col_index in range(sheet.ncols):
            cell = sheet.cell(row_index, col_index)
            if cell.ctype == xlrd.XL_CELL_DATE:
                try:
                    dt = xlrd.xldate_as_datetime(cell.value, workbook.datemode)
                    value = dt.strftime("%d.%m.%Y %H:%M") if dt.hour or dt.minute else dt.strftime("%d.%m.%Y")
                except Exception:
                    value = str(cell.value)
            elif cell.ctype == xlrd.XL_CELL_NUMBER:
                int_val = int(cell.value)
                value = str(int_val) if cell.value == int_val else str(cell.value)
            else:
                value = str(cell.value)
            row_values.append(value)
        if not any(v.strip() for v in row_values):
            continue
        rows.append(row_values)
        row_numbers.append(row_index + 1)
        max_columns = max(max_columns, len(row_values))
        if preview_limit is not None and len(rows) >= preview_limit:
            break

    columns = [column_index_to_letter(index) for index in range(1, max_columns + 1)]
    return columns, rows, row_numbers


_CSV_SNIFF_BYTES = 8192
_CSV_CANDIDATE_DELIMITERS = ",;\t|"


def split_single_cell_rows_by_delimiter(rows: list[list]) -> tuple[list[list], str]:
    if not isinstance(rows, list) or not rows:
        return rows, ""

    non_empty_rows = [row for row in rows if isinstance(row, list) and any(str(value or "").strip() for value in row)]
    if len(non_empty_rows) < 2:
        return rows, ""

    if any(len(row) > 1 for row in non_empty_rows):
        return rows, ""

    for delimiter in _CSV_CANDIDATE_DELIMITERS:
        parsed_rows = []
        parsed_widths = set()
        valid_candidate = True

        for row in rows:
            row_values = row if isinstance(row, list) else [row]
            first_value = str(row_values[0] if row_values else "")

            if not first_value.strip():
                parsed_rows.append([""])
                continue

            parsed_row = next(csv.reader([first_value], delimiter=delimiter, skipinitialspace=True))
            if len(parsed_row) <= 1:
                valid_candidate = False
                break

            parsed_widths.add(len(parsed_row))
            parsed_rows.append(parsed_row)

        if valid_candidate and len(parsed_widths) == 1:
            return parsed_rows, delimiter

    return rows, ""


def build_columns_from_rows(rows: list[list]) -> list[str]:
    max_columns = max((len(row) for row in rows if isinstance(row, list)), default=0)
    return [column_index_to_letter(index) for index in range(1, max_columns + 1)]


def detect_csv_delimiter(raw_bytes: bytes) -> str:
    sample = raw_bytes.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=_CSV_CANDIDATE_DELIMITERS)
        return dialect.delimiter
    except csv.Error:
        return ","


def extract_rows_from_csv(session: ImportSession, preview_limit: int | None = 20):
    try:
        with session.stored_file.open("rb") as stored_file:
            sample_bytes = stored_file.read(_CSV_SNIFF_BYTES)
            stored_file.seek(0)
            delimiter = detect_csv_delimiter(sample_bytes)
            text_file = TextIOWrapper(stored_file, encoding="utf-8-sig", newline="")
            reader = csv.reader(text_file, delimiter=delimiter)
            rows = []
            row_numbers = []
            max_columns = 0
            for row_index, row in enumerate(reader, start=1):
                rows.append(row)
                row_numbers.append(row_index)
                max_columns = max(max_columns, len(row))
                if preview_limit is not None and len(rows) >= preview_limit:
                    break
    except OSError as error:
        raise ValueError("Unable to read workbook preview") from error

    rows, detected_delimiter = split_single_cell_rows_by_delimiter(rows)
    columns = build_columns_from_rows(rows)
    if detected_delimiter:
        delimiter = detected_delimiter
    return columns, rows, row_numbers, delimiter


def extract_preview_rows_with_meta(session: ImportSession, selected_sheet_name: str, preview_limit: int | None = 20):
    """Like extract_preview_rows but returns extra metadata (e.g. detected CSV delimiter)."""
    if session.source_format == ImportSession.SourceFormat.CSV:
        columns, rows, row_numbers, delimiter = extract_rows_from_csv(session, preview_limit=preview_limit)
        return columns, rows, row_numbers, {"csv_delimiter": delimiter}
    columns, rows, row_numbers = extract_preview_rows(session, selected_sheet_name, preview_limit=preview_limit)
    return columns, rows, row_numbers, {}


def extract_preview_rows(session: ImportSession, selected_sheet_name: str, preview_limit: int | None = 20):
    if not session.stored_file:
        raise ValueError("Uploaded file is required")

    if session.source_format == ImportSession.SourceFormat.CSV:
        if selected_sheet_name != "CSV":
            raise ValueError("Selected sheet does not exist")
        columns, rows, row_numbers, _delimiter = extract_rows_from_csv(session, preview_limit=preview_limit)
        return columns, rows, row_numbers

    if session.source_format == ImportSession.SourceFormat.XLS:
        _columns, rows, row_numbers = extract_rows_from_xls(session, selected_sheet_name, preview_limit=preview_limit)
        rows, _detected_delimiter = split_single_cell_rows_by_delimiter(rows)
        return build_columns_from_rows(rows), rows, row_numbers

    if session.source_format != ImportSession.SourceFormat.XLSX:
        raise ValueError("Unsupported source format")

    sheets, worksheet_files, shared_strings_xml, styles_xml = read_xlsx_archive(session)
    selected_sheet = next((sheet for sheet in sheets if sheet["name"] == selected_sheet_name), None)
    if selected_sheet is None:
        raise ValueError("Selected sheet does not exist")

    sheet_xml = worksheet_files.get(selected_sheet["path"])
    if sheet_xml is None:
        raise ValueError("Unable to read workbook preview")

    shared_strings = parse_shared_strings(shared_strings_xml)
    date_style_formats = parse_xlsx_date_style_formats(styles_xml)
    _columns, rows, row_numbers = extract_rows_from_xlsx_sheet(
        sheet_xml,
        shared_strings=shared_strings,
        date_style_formats=date_style_formats,
        preview_limit=preview_limit,
    )
    rows, _detected_delimiter = split_single_cell_rows_by_delimiter(rows)
    return build_columns_from_rows(rows), rows, row_numbers


def row_has_values(row_values) -> bool:
    return any(str(value).strip() for value in row_values)


def normalize_headers(columns, header_values):
    return [
        str(header_values[index]).strip() if index < len(header_values) and str(header_values[index]).strip() else f"Column {column_name}"
        for index, column_name in enumerate(columns)
    ]


def detect_preview_structure(columns, preview_rows, row_numbers):
    if not columns:
        return {
            "header_row": 1,
            "data_start_row": 2,
            "headers": [],
        }

    header_index = next(
        (index for index, row in enumerate(preview_rows) if row_has_values(row)),
        None,
    )
    if header_index is None:
        return {
            "header_row": 1,
            "data_start_row": 2,
            "headers": [f"Column {column_name}" for column_name in columns],
        }

    header_row = row_numbers[header_index] if header_index < len(row_numbers) else header_index + 1
    header_values = preview_rows[header_index]
    data_index = next(
        (index for index in range(header_index + 1, len(preview_rows)) if row_has_values(preview_rows[index])),
        None,
    )
    data_start_row = row_numbers[data_index] if data_index is not None and data_index < len(row_numbers) else header_row + 1

    return {
        "header_row": header_row,
        "data_start_row": data_start_row,
        "headers": normalize_headers(columns, header_values),
    }


def get_row_values_by_number(preview_rows, row_numbers, target_row_number):
    for index, row_number in enumerate(row_numbers):
        if row_number == target_row_number and index < len(preview_rows):
            return preview_rows[index]
    return None


def collect_unique_non_empty_values(values) -> list[str]:
    observed_values = []
    seen_values = set()

    for value in values:
        normalized_value = str(value or "").strip()
        if not normalized_value or normalized_value in seen_values:
            continue

        seen_values.add(normalized_value)
        observed_values.append(normalized_value)

    return observed_values


def build_observed_mapping_values(rows, row_numbers, data_start_row: int, fields: list[dict], mapping: dict) -> dict[str, list[str]]:
    if not isinstance(mapping, dict) or not mapping:
        return {}

    field_index = {
        str(field.get("id")): field
        for field in fields
        if isinstance(field, dict) and str(field.get("id") or "").strip()
    }
    observed_values = {}

    for target_field_id, mapping_item in mapping.items():
        field = field_index.get(str(target_field_id))
        field_items = field.get("items") if isinstance(field, dict) else []
        if not isinstance(field_items, list) or not field_items:
            continue
        if not isinstance(mapping_item, dict):
            continue

        column_index = column_letter_to_index(str(mapping_item.get("column") or "")) - 1
        if column_index < 0:
            continue

        source_values = []
        for index, row in enumerate(rows):
            row_number = row_numbers[index] if index < len(row_numbers) else index + 1
            if row_number < data_start_row:
                continue

            source_values.append(row[column_index] if column_index < len(row) else "")

        unique_values = collect_unique_non_empty_values(source_values)
        if unique_values:
            observed_values[str(target_field_id)] = unique_values

    return observed_values


def mapping_has_observed_value_fields(fields: list[dict], mapping: dict) -> bool:
    if not isinstance(mapping, dict) or not mapping:
        return False

    field_index = {
        str(field.get("id")): field
        for field in fields
        if isinstance(field, dict) and str(field.get("id") or "").strip()
    }

    for target_field_id in mapping.keys():
        field = field_index.get(str(target_field_id))
        field_items = field.get("items") if isinstance(field, dict) else []
        if isinstance(field_items, list) and field_items:
            return True

    return False


def build_unmapped_mapping_values(observed_values: dict[str, list[str]], mapping: dict, fields: list[dict]) -> dict[str, list[str]]:
    if not isinstance(observed_values, dict) or not isinstance(mapping, dict):
        return {}

    field_index = {
        str(field.get("id")): field
        for field in fields
        if isinstance(field, dict) and str(field.get("id") or "").strip()
    }
    unmapped_values = {}

    for target_field_id, field_values in observed_values.items():
        mapping_item = mapping.get(str(target_field_id))
        field = field_index.get(str(target_field_id), {})
        value_mapping = mapping_item.get("value_mapping") if isinstance(mapping_item, dict) else None
        mapped_source_values = {
            str(source_value).strip()
            for source_value, target_value in (value_mapping or {}).items()
            if str(source_value).strip() and str(target_value).strip()
        }
        missing_values = [
            str(source_value).strip()
            for source_value in field_values
            if (
                str(source_value).strip()
                and str(source_value).strip() not in mapped_source_values
                and not resolve_field_item_value(field, source_value)
            )
        ]
        if missing_values:
            unmapped_values[str(target_field_id)] = missing_values

    return unmapped_values


def normalize_session_entity_config(entity_type: str, payload) -> dict:
    if entity_type == SMART_PROCESS_ENTITY_TYPE:
        payload_dict = payload if isinstance(payload, dict) else {}
        raw_entity_config = payload_dict.get("entity_config")
        if isinstance(raw_entity_config, dict):
            return normalize_smart_process_entity_config(raw_entity_config)
        return normalize_smart_process_entity_config(payload_dict)
    return {}


def get_session_entity_config(session: ImportSession) -> dict:
    import_settings = session.import_settings if isinstance(session.import_settings, dict) else {}
    entity_config = import_settings.get("entity_config")
    return entity_config if isinstance(entity_config, dict) else {}


def fetch_session_entity_fields(account, session: ImportSession) -> list[dict]:
    return fetch_entity_fields(
        account,
        session.entity_type,
        entity_config=get_session_entity_config(session),
    )


def load_session_preflight_context(
    account,
    session: ImportSession,
    *,
    columns: list[str],
    selected_sheet_name: str,
    mapping: dict,
    dedup_settings,
    default_field_values: dict | None,
    data_start_row: int,
) -> tuple[list[dict], list[list], list[int], dict]:
    fields = fetch_session_entity_fields(account, session)
    _columns, rows, row_numbers = extract_preview_rows(session, str(selected_sheet_name), preview_limit=None)
    preflight = build_mapping_preflight(
        entity_type=session.entity_type,
        rows=rows,
        row_numbers=row_numbers,
        columns=columns,
        data_start_row=data_start_row,
        mapping=mapping,
        fields=fields,
        dedup_settings=dedup_settings,
        default_field_values=default_field_values,
    )
    return fields, rows, row_numbers, preflight


def calculate_import_total_rows(session: ImportSession, selected_sheet_name: str, data_start_row: int) -> int:
    _columns, _rows, row_numbers = extract_preview_rows(session, str(selected_sheet_name), preview_limit=None)
    return sum(1 for row_number in row_numbers if row_number >= data_start_row)


def build_field_title_map(fields: list[dict]) -> dict[str, str]:
    return {
        str(field.get("id") or ""): str(field.get("title") or field.get("id") or "")
        for field in fields
        if isinstance(field, dict) and field.get("id")
    }


def build_session_alias_rule_payloads(account, session: ImportSession, fields: list[dict]) -> list[dict]:
    alias_rules = load_portal_alias_rules(
        session.portal_member_id,
        session.portal_domain,
        entity_type=session.entity_type,
        entity_scope_key=build_template_entity_scope(session.entity_type, get_session_entity_config(session)),
    )
    field_titles = build_field_title_map(fields)
    return [serialize_alias_rule(item, field_titles) for item in alias_rules]


def count_mapping_values(values_by_field: dict[str, list[str]]) -> int:
    if not isinstance(values_by_field, dict):
        return 0

    return sum(
        len(values)
        for values in values_by_field.values()
        if isinstance(values, list)
    )


def parse_positive_int(value, field_name):
    if value in (None, ""):
        return None

    try:
        parsed_value = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a positive integer") from error

    if parsed_value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")

    return parsed_value


_STUCK_SESSION_TIMEOUT_MINUTES = 90


def release_stuck_sessions(portal_member_id: str, portal_domain: str) -> int:
    cutoff = timezone.now() - timedelta(minutes=_STUCK_SESSION_TIMEOUT_MINUTES)
    stuck = ImportSession.objects.filter(
        portal_member_id=portal_member_id,
        portal_domain=portal_domain,
        status=ImportSession.Status.RUNNING,
        updated_at__lt=cutoff,
    )
    count = stuck.update(
        status=ImportSession.Status.FAILED,
        last_error=f"Сессия автоматически остановлена: не было активности более {_STUCK_SESSION_TIMEOUT_MINUTES} минут",
    )
    return count


def apply_preview_structure_overrides(columns, preview_rows, row_numbers, structure, payload):
    header_row = parse_positive_int(payload.get("header_row"), "Header row") or structure["header_row"]
    data_start_row = parse_positive_int(payload.get("data_start_row"), "Data start row") or structure["data_start_row"]

    if data_start_row <= header_row:
        raise ValueError("Data start row must be greater than header row")

    header_values = get_row_values_by_number(preview_rows, row_numbers, header_row)
    if header_values is None:
        raise ValueError("Header row is outside preview range")

    return {
        "header_row": header_row,
        "data_start_row": data_start_row,
        "headers": normalize_headers(columns, header_values),
    }


@xframe_options_exempt
@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE"])
@log_errors("import_sessions")
@auth_required
def import_sessions(request: AuthorizedRequest):
    account = request.bitrix24_account
    portal_member_id = getattr(account, "member_id", "")
    portal_domain = getattr(account, "domain_url", "")

    if request.method == "GET":
        if not has_permission(account, "sessions.view"):
            return permission_denied_response()

        release_stuck_sessions(portal_member_id, portal_domain)

        sessions = ImportSession.objects.filter(
            portal_member_id=portal_member_id,
        ).order_by("-created_at")

        return JsonResponse({"items": [serialize_session_history_item(item) for item in sessions]})

    if request.method == "DELETE":
        if not has_permission(account, "sessions.create"):
            return permission_denied_response()

        deletable_statuses = [
            ImportSession.Status.COMPLETED,
            ImportSession.Status.FAILED,
            ImportSession.Status.CANCELLED,
            ImportSession.Status.UPLOADED,
            ImportSession.Status.VALIDATED,
            ImportSession.Status.DRAFT,
        ]
        sessions_to_delete = ImportSession.objects.filter(
            portal_member_id=portal_member_id,
            status__in=deletable_statuses,
        )
        deleted_count = 0
        for session in sessions_to_delete:
            try:
                if session.stored_file and session.stored_file.name:
                    try:
                        session.stored_file.delete(save=False)
                    except Exception:
                        pass
                session.delete()
                deleted_count += 1
            except Exception as exc:
                logging.warning("Failed to delete session %s: %s", session.id, exc)

        return JsonResponse({"deleted": deleted_count})

    if not has_permission(account, "sessions.create"):
        return permission_denied_response()

    payload = request.data or {}
    entity_type = payload.get("entity_type")
    source_format = payload.get("source_format")
    original_filename = payload.get("original_filename")

    missing_fields = [
        field_name
        for field_name, value in {
            "entity_type": entity_type,
            "source_format": source_format,
            "original_filename": original_filename,
        }.items()
        if not value
    ]
    if missing_fields:
        return JsonResponse(
            {"error": f"Missing required fields: {', '.join(missing_fields)}"},
            status=400,
        )

    try:
        entity_config = normalize_session_entity_config(str(entity_type or "").strip(), payload)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    import_mode = normalize_import_mode(payload.get("import_mode"))

    session = ImportSession.objects.create(
        portal_member_id=portal_member_id,
        portal_domain=portal_domain,
        created_by_b24_user_id=getattr(account, "b24_user_id", 0),
        entity_type=entity_type,
        source_format=source_format,
        status=ImportSession.Status.DRAFT,
        original_filename=original_filename,
        import_settings={
            **({"entity_config": entity_config} if entity_config else {}),
            "import_mode": import_mode,
        },
    )

    return JsonResponse({"item": serialize_session(session)}, status=201)


@xframe_options_exempt
@csrf_exempt
@require_http_methods(["GET", "POST"])
@log_errors("import_templates")
@auth_required
def import_templates(request: AuthorizedRequest):
    account = request.bitrix24_account
    portal_member_id = getattr(account, "member_id", "")
    portal_domain = getattr(account, "domain_url", "")

    if request.method == "GET":
        if not has_permission(account, "templates.manage"):
            return permission_denied_response()

        entity_type = str((request.GET or {}).get("entity_type") or "").strip()
        entity_config = {}
        if entity_type == SMART_PROCESS_ENTITY_TYPE:
            try:
                entity_config = normalize_session_entity_config(entity_type, request.GET)
            except ValueError as error:
                return JsonResponse({"error": str(error)}, status=400)

        templates = ImportTemplate.objects.filter(
            portal_member_id=portal_member_id,
            portal_domain=portal_domain,
            is_active=True,
        )
        if entity_type:
            templates = templates.filter(entity_type=entity_type)
        if entity_type == SMART_PROCESS_ENTITY_TYPE and entity_config:
            templates = templates.filter(entity_scope_key=build_template_entity_scope(entity_type, entity_config))

        return JsonResponse({"items": [serialize_template(item) for item in templates.order_by("name")]})

    payload = request.data or {}
    template_name = str(payload.get("name") or "").strip()
    session_id = payload.get("session_id")

    if not template_name:
        return JsonResponse({"error": "Template name is required"}, status=400)
    if not session_id:
        return JsonResponse({"error": "session_id is required"}, status=400)

    session = load_portal_session(portal_member_id, portal_domain, session_id)
    if session is None:
        return JsonResponse({"error": "Import session not found"}, status=404)
    if not has_permission(account, "templates.manage") or not can_edit_session(account, session):
        return permission_denied_response()

    import_settings = session.import_settings if isinstance(session.import_settings, dict) else {}
    preview_data = session.preview_data if isinstance(session.preview_data, dict) else {}
    headers = preview_data.get("headers")
    columns = preview_data.get("columns")

    mapping_payload = (payload if isinstance(payload, dict) else {})
    if "mapping" in mapping_payload:
        if not isinstance(headers, list) or not isinstance(columns, list) or not headers:
            return JsonResponse({"error": "Preview data is required before template save"}, status=400)

        try:
            fields = fetch_session_entity_fields(account, session)
            saved_mapping = normalize_saved_mapping(mapping_payload.get("mapping", {}), headers, columns, fields)
        except ValueError as error:
            return JsonResponse({"error": str(error)}, status=400)
    else:
        saved_mapping = import_settings.get("mapping", {})
        if not isinstance(saved_mapping, dict):
            saved_mapping = {}

    if not saved_mapping:
        return JsonResponse({"error": "Saved mapping is required before template save"}, status=400)
    try:
        saved_dedup = normalize_entity_dedup_settings(session.entity_type, mapping_payload.get("dedup", import_settings.get("dedup", {})))
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    selected_sheet_name = session.source_sheet_name or (
        session.preview_data.get("selected_sheet_name")
        if isinstance(session.preview_data, dict)
        else ""
    )
    if not selected_sheet_name:
        return JsonResponse({"error": "Preview data is required before template save"}, status=400)

    template_entity_config = build_template_entity_config(session.entity_type, get_session_entity_config(session))
    template_entity_scope = build_template_entity_scope(session.entity_type, template_entity_config)
    template, _created = ImportTemplate.objects.update_or_create(
        portal_member_id=portal_member_id,
        portal_domain=portal_domain,
        entity_type=session.entity_type,
        entity_scope_key=template_entity_scope,
        name=template_name,
        defaults={
            "entity_config": template_entity_config,
            "mapping_schema": saved_mapping,
            "column_settings": {
                "sheet_name": selected_sheet_name,
                "header_row": session.header_row,
                "data_start_row": session.data_start_row,
            },
            "dedup_settings": saved_dedup,
            "is_active": True,
        },
    )

    return JsonResponse({"item": serialize_template(template)}, status=201)


@xframe_options_exempt
@csrf_exempt
@require_http_methods(["GET", "POST"])
@log_errors("import_alias_rules")
@auth_required
def import_alias_rules(request: AuthorizedRequest):
    account = request.bitrix24_account
    portal_member_id = getattr(account, "member_id", "")
    portal_domain = getattr(account, "domain_url", "")

    if not has_permission(account, "templates.manage"):
        return permission_denied_response()

    if request.method == "GET":
        entity_type = str((request.GET or {}).get("entity_type") or "").strip()
        if not entity_type:
            return JsonResponse({"items": []})
        if is_simple_import_mode((request.GET or {}).get("import_mode")):
            return JsonResponse({"items": []})

        entity_config = {}
        if entity_type == SMART_PROCESS_ENTITY_TYPE:
            try:
                entity_config = normalize_session_entity_config(entity_type, request.GET)
            except ValueError as error:
                return JsonResponse({"error": str(error)}, status=400)

        try:
            fields = fetch_entity_fields(account, entity_type, entity_config=entity_config)
        except ValueError as error:
            return JsonResponse({"error": str(error)}, status=400)

        field_titles = {
            str(field.get("id") or ""): str(field.get("title") or field.get("id") or "")
            for field in fields
            if isinstance(field, dict) and field.get("id")
        }
        alias_rules = load_portal_alias_rules(
            portal_member_id,
            portal_domain,
            entity_type=entity_type,
            entity_scope_key=build_template_entity_scope(entity_type, entity_config),
        )
        return JsonResponse({"items": [serialize_alias_rule(item, field_titles) for item in alias_rules]})

    payload = request.data or {}
    source_label = str(payload.get("source_label") or "").strip()
    target_field_id = str(payload.get("target_field_id") or "").strip()
    session_id = payload.get("session_id")

    if not session_id:
        return JsonResponse({"error": "session_id is required"}, status=400)
    if not source_label:
        return JsonResponse({"error": "source_label is required"}, status=400)
    if not target_field_id:
        return JsonResponse({"error": "target_field_id is required"}, status=400)

    session = load_portal_session(portal_member_id, portal_domain, session_id)
    if session is None:
        return JsonResponse({"error": "Import session not found"}, status=404)
    if not can_edit_session(account, session):
        return permission_denied_response()

    try:
        fields = fetch_session_entity_fields(account, session)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    field_titles = {
        str(field.get("id") or ""): str(field.get("title") or field.get("id") or "")
        for field in fields
        if isinstance(field, dict) and field.get("id")
    }
    if target_field_id not in field_titles:
        return JsonResponse({"error": "Unknown target field"}, status=400)

    normalized_source_label = normalize_mapping_value(source_label)
    if not normalized_source_label:
        return JsonResponse({"error": "source_label must contain letters or numbers"}, status=400)

    alias_rule, _created = ImportAliasRule.objects.update_or_create(
        portal_member_id=portal_member_id,
        portal_domain=portal_domain,
        entity_type=session.entity_type,
        entity_scope_key=build_template_entity_scope(session.entity_type, get_session_entity_config(session)),
        normalized_source_label=normalized_source_label,
        defaults={
            "source_label": source_label,
            "target_field_id": target_field_id,
            "created_by_b24_user_id": getattr(account, "b24_user_id", 0),
            "is_active": True,
        },
    )

    return JsonResponse({"item": serialize_alias_rule(alias_rule, field_titles)}, status=201)


@xframe_options_exempt
@csrf_exempt
@require_http_methods(["POST"])
@log_errors("import_session_apply_template")
@auth_required
def import_session_apply_template(request: AuthorizedRequest, session_id):
    account = request.bitrix24_account
    portal_member_id = getattr(account, "member_id", "")
    portal_domain = getattr(account, "domain_url", "")

    session = load_portal_session(portal_member_id, portal_domain, session_id)
    if session is None:
        return JsonResponse({"error": "Import session not found"}, status=404)
    if not has_permission(account, "templates.manage") or not can_edit_session(account, session):
        return permission_denied_response()

    template_id = (request.data or {}).get("template_id")
    if not template_id:
        return JsonResponse({"error": "template_id is required"}, status=400)

    template = load_portal_template(
        portal_member_id,
        portal_domain,
        template_id,
        entity_type=session.entity_type,
        entity_scope_key=build_template_entity_scope(session.entity_type, get_session_entity_config(session)),
    )
    if template is None:
        return JsonResponse({"error": "Import template not found"}, status=404)

    try:
        sheet_names = extract_sheet_names(session)
        column_settings = template.column_settings if isinstance(template.column_settings, dict) else {}
        configured_sheet_name = str(column_settings.get("sheet_name") or "").strip()
        selected_sheet_name = configured_sheet_name if configured_sheet_name in sheet_names else sheet_names[0]
        columns, preview_rows, row_numbers = extract_preview_rows(session, selected_sheet_name)
        structure = detect_preview_structure(columns, preview_rows, row_numbers)
        structure = apply_preview_structure_overrides(
            columns,
            preview_rows,
            row_numbers,
            structure,
            {
                "header_row": column_settings.get("header_row"),
                "data_start_row": column_settings.get("data_start_row"),
            },
        )
        fields = fetch_session_entity_fields(account, session)
        alias_rules = load_portal_alias_rules(
            portal_member_id,
            portal_domain,
            entity_type=session.entity_type,
            entity_scope_key=build_template_entity_scope(session.entity_type, get_session_entity_config(session)),
        )
        saved_mapping = normalize_saved_mapping(
            template.mapping_schema if isinstance(template.mapping_schema, dict) else {},
            structure["headers"],
            columns,
            fields,
        )
        saved_dedup = normalize_entity_dedup_settings(
            session.entity_type,
            template.dedup_settings if isinstance(template.dedup_settings, dict) else {}
        )
        candidate_bundle = build_candidate_mapping_bundle(
            structure["headers"],
            columns,
            fields,
            alias_rules=[
                {
                    "normalized_source_label": rule.normalized_source_label,
                    "target_field_id": rule.target_field_id,
                }
                for rule in alias_rules
            ],
        )
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    try:
        _columns, full_rows, full_row_numbers = extract_preview_rows(session, str(selected_sheet_name), preview_limit=None)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    preflight = build_mapping_preflight(
        entity_type=session.entity_type,
        rows=full_rows,
        row_numbers=full_row_numbers,
        columns=columns,
        data_start_row=max(1, int(structure["data_start_row"] or 1)),
        mapping=saved_mapping if saved_mapping else candidate_bundle["mapping"],
        fields=fields,
        dedup_settings=saved_dedup,
        default_field_values=build_task_default_field_values(session.entity_type, normalize_task_defaults(session.import_settings.get("task_defaults", {}))) if isinstance(session.import_settings, dict) else {},
    )

    session.source_sheet_name = selected_sheet_name
    session.header_row = structure["header_row"]
    session.data_start_row = structure["data_start_row"]
    session.preview_data = {
        "sheet_names": sheet_names,
        "selected_sheet_name": selected_sheet_name,
        "columns": columns,
        "preview_rows": preview_rows,
        "header_row": structure["header_row"],
        "data_start_row": structure["data_start_row"],
        "headers": structure["headers"],
    }
    session.import_settings = {
        **build_mode_scoped_import_settings(
            session.import_settings,
            import_mode=IMPORT_MODE_ADVANCED,
            mapping=saved_mapping,
            dedup=saved_dedup,
            task_defaults=normalize_task_defaults(
                (session.import_settings if isinstance(session.import_settings, dict) else {}).get("task_defaults", {}),
            ),
        ),
        "applied_template_id": str(template.id),
    }
    session.last_error = ""
    session.save(
        update_fields=[
            "source_sheet_name",
            "header_row",
            "data_start_row",
            "preview_data",
            "import_settings",
            "last_error",
            "updated_at",
        ]
    )

    return JsonResponse(
        {
            "item": {
                "session_id": str(session.id),
                "applied_template_id": str(template.id),
                "header_row": structure["header_row"],
                "data_start_row": structure["data_start_row"],
                "headers": structure["headers"],
                "columns": columns,
                "saved_mapping": saved_mapping,
                "saved_dedup": saved_dedup,
                "candidate_mapping": candidate_bundle["mapping"],
                "candidate_suggestions": candidate_bundle["suggestions"],
                "alias_rules": build_session_alias_rule_payloads(account, session, fields),
                "preflight": preflight,
            }
        }
    )


@xframe_options_exempt
@require_GET
@log_errors("import_session_detail")
@auth_required
def import_session_detail(request: AuthorizedRequest, session_id):
    account = request.bitrix24_account
    portal_member_id = getattr(account, "member_id", "")
    portal_domain = getattr(account, "domain_url", "")

    session = load_portal_session(portal_member_id, portal_domain, session_id)
    if session is None:
        return JsonResponse({"error": "Import session not found"}, status=404)
    if not can_view_session(account, session):
        return permission_denied_response()

    return JsonResponse({"item": serialize_session(session)})


@xframe_options_exempt
@require_GET
@log_errors("import_departments")
@auth_required
def import_departments(request: AuthorizedRequest):
    from b24pysdk.bitrix_api.requests import BitrixAPIRequest
    from .services.import_execution import unwrap_bitrix_result

    account = request.bitrix24_account
    response = BitrixAPIRequest(
        bitrix_token=account,
        api_method="department.get",
        params={"select": ["ID", "NAME", "PARENT", "SORT"]},
    )
    raw = unwrap_bitrix_result(response)
    items = []
    for item in (raw if isinstance(raw, list) else []):
        if not isinstance(item, dict):
            continue
        dept_id = str(item.get("ID") or item.get("id") or "").strip()
        name = str(item.get("NAME") or item.get("name") or "").strip()
        parent = str(item.get("PARENT") or item.get("parent") or "").strip()
        if not dept_id:
            continue
        items.append({"id": dept_id, "name": name, "parent_id": parent or None})

    items.sort(key=lambda d: (d["parent_id"] is not None, d["name"].lower()))
    return JsonResponse({"items": items})


@xframe_options_exempt
@require_GET
@log_errors("import_fields")
@auth_required
def import_fields(request: AuthorizedRequest):
    if not has_permission(request.bitrix24_account, "sessions.view"):
        return permission_denied_response()

    request_payload = {
        **((request.GET or {}) if hasattr(request, "GET") else {}),
        **((request.data or {}) if isinstance(request.data, dict) else {}),
    }

    entity_type = request_payload.get("entity_type")
    if not entity_type:
        return JsonResponse({"error": "entity_type is required"}, status=400)

    try:
        entity_type_str = str(entity_type)
        entity_config = normalize_session_entity_config(entity_type_str, request_payload)
        linked_entities = build_linked_entities_payload(entity_type_str)
        items = fetch_entity_fields(
            request.bitrix24_account,
            entity_type_str,
            entity_config=entity_config,
        )
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    return JsonResponse(
        {
            "entity_type": entity_type_str,
            **({"entity_config": entity_config} if entity_config else {}),
            **({"linked_entities": linked_entities} if linked_entities else {}),
            "items": items,
        }
    )


@xframe_options_exempt
@require_GET
@log_errors("import_smart_processes")
@auth_required
def import_smart_processes(request: AuthorizedRequest):
    if not has_permission(request.bitrix24_account, "sessions.create"):
        return permission_denied_response()

    try:
        items = fetch_smart_process_types(request.bitrix24_account)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    return JsonResponse({"items": items})


@xframe_options_exempt
@csrf_exempt
@require_http_methods(["GET", "PATCH"])
@log_errors("import_session_mapping")
@auth_required
def import_session_mapping(request: AuthorizedRequest, session_id):
    account = request.bitrix24_account
    portal_member_id = getattr(account, "member_id", "")
    portal_domain = getattr(account, "domain_url", "")

    session = load_portal_session(portal_member_id, portal_domain, session_id)
    if session is None:
        return JsonResponse({"error": "Import session not found"}, status=404)
    if request.method == "GET":
        if not can_view_session(account, session):
            return permission_denied_response()
    elif not can_edit_session(account, session):
        return permission_denied_response()

    preview_data = session.preview_data if isinstance(session.preview_data, dict) else {}
    headers = preview_data.get("headers")
    columns = preview_data.get("columns")
    if not isinstance(headers, list) or not isinstance(columns, list) or not headers:
        return JsonResponse({"error": "Preview data is required before mapping"}, status=400)

    try:
        fields = fetch_session_entity_fields(account, session)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    import_mode_source = request.GET if request.method == "GET" else request.data
    requested_import_mode = normalize_import_mode((import_mode_source or {}).get("import_mode"))
    use_alias_rules = not is_simple_import_mode(requested_import_mode)
    alias_rules = load_portal_alias_rules(
        portal_member_id,
        portal_domain,
        entity_type=session.entity_type,
        entity_scope_key=build_template_entity_scope(session.entity_type, get_session_entity_config(session)),
    ) if use_alias_rules else []
    candidate_bundle = build_candidate_mapping_bundle(
        headers,
        columns,
        fields,
        alias_rules=[
            {
                "normalized_source_label": rule.normalized_source_label,
                "target_field_id": rule.target_field_id,
            }
            for rule in alias_rules
        ],
    )
    import_settings = session.import_settings if isinstance(session.import_settings, dict) else {}
    _resolved_import_mode, saved_mapping, saved_dedup_source, saved_task_defaults_source = resolve_session_mode_settings(
        import_settings,
        requested_import_mode,
    )
    task_defaults = normalize_task_defaults(saved_task_defaults_source)
    try:
        saved_dedup = normalize_entity_dedup_settings(session.entity_type, saved_dedup_source)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    if request.method == "PATCH":
        try:
            saved_mapping = normalize_saved_mapping(
                (request.data or {}).get("mapping", {}),
                headers,
                columns,
                fields,
            )
            saved_dedup = normalize_entity_dedup_settings(session.entity_type, (request.data or {}).get("dedup", import_settings.get("dedup", {})))
            task_defaults = normalize_task_defaults(
                {
                    "default_responsible_id": (request.data or {}).get("default_responsible_id"),
                    "default_creator_id": (request.data or {}).get("default_creator_id"),
                    "default_comment_author_id": (request.data or {}).get("default_comment_author_id"),
                    "task_defaults": saved_task_defaults_source,
                },
                account=account,
            )
        except ValueError as error:
            return JsonResponse({"error": str(error)}, status=400)

        session.import_settings = build_mode_scoped_import_settings(
            import_settings,
            import_mode=requested_import_mode,
            mapping=saved_mapping,
            dedup=saved_dedup,
            task_defaults=task_defaults,
        )
        session.last_error = ""
        session.save(update_fields=["import_settings", "last_error", "updated_at"])

    observed_values = {}
    selected_sheet_name = preview_data.get("selected_sheet_name") or session.source_sheet_name
    mapping_for_observed_values = saved_mapping if saved_mapping else candidate_bundle["mapping"]
    default_field_values = build_task_default_field_values(session.entity_type, task_defaults)
    preflight = {
        "blocking_issue_count": 0,
        "warning_count": 0,
        "issues": [],
    }
    try:
        task_user_options = list_bitrix_users(account) if session.entity_type in {
            ImportSession.EntityType.TASK,
            ImportSession.EntityType.TASK_COMMENT,
        } else []
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    full_rows = []
    full_row_numbers = []
    if selected_sheet_name:
        try:
            _columns, full_rows, full_row_numbers = extract_preview_rows(session, str(selected_sheet_name), preview_limit=None)
        except ValueError as error:
            return JsonResponse({"error": str(error)}, status=400)

        if mapping_has_observed_value_fields(fields, mapping_for_observed_values):
            observed_values = build_observed_mapping_values(
                rows=full_rows,
                row_numbers=full_row_numbers,
                data_start_row=max(1, int(session.data_start_row or preview_data.get("data_start_row") or 1)),
                fields=fields,
                mapping=mapping_for_observed_values,
            )

        preflight = build_mapping_preflight(
            entity_type=session.entity_type,
            rows=full_rows,
            row_numbers=full_row_numbers,
            columns=columns,
            data_start_row=max(1, int(session.data_start_row or preview_data.get("data_start_row") or 1)),
            mapping=mapping_for_observed_values,
            fields=fields,
            dedup_settings=saved_dedup,
            default_field_values=default_field_values,
        )

    unmapped_values = build_unmapped_mapping_values(observed_values, mapping_for_observed_values, fields)
    linked_entities = build_linked_entities_payload(session.entity_type)

    return JsonResponse(
        {
            "item": {
                "session_id": str(session.id),
                "entity_type": session.entity_type,
                "headers": headers,
                "columns": columns,
                "fields": fields,
                "candidate_mapping": candidate_bundle["mapping"],
                "candidate_suggestions": candidate_bundle["suggestions"],
                "saved_mapping": saved_mapping,
                "saved_dedup": saved_dedup,
                "task_defaults": task_defaults,
                "task_user_options": task_user_options,
                "alias_rules": [serialize_alias_rule(item, build_field_title_map(fields)) for item in alias_rules],
                **({"linked_entities": linked_entities} if linked_entities else {}),
                "observed_values": observed_values,
                "unmapped_values": unmapped_values,
                "unmapped_value_count": count_mapping_values(unmapped_values),
                "preflight": preflight,
            }
        }
    )


@xframe_options_exempt
@csrf_exempt
@require_http_methods(["POST"])
@log_errors("import_session_validate")
@auth_required
def import_session_validate(request: AuthorizedRequest, session_id):
    account = request.bitrix24_account
    portal_member_id = getattr(account, "member_id", "")
    portal_domain = getattr(account, "domain_url", "")

    session = load_portal_session(portal_member_id, portal_domain, session_id)
    if session is None:
        return JsonResponse({"error": "Import session not found"}, status=404)
    if not can_run_session(account, session):
        return permission_denied_response()

    preview_data = session.preview_data if isinstance(session.preview_data, dict) else {}
    headers = preview_data.get("headers")
    columns = preview_data.get("columns")
    selected_sheet_name = preview_data.get("selected_sheet_name") or session.source_sheet_name
    if not isinstance(headers, list) or not isinstance(columns, list) or not headers or not selected_sheet_name:
        return JsonResponse({"error": "Preview data is required before validation"}, status=400)

    import_settings = session.import_settings if isinstance(session.import_settings, dict) else {}
    saved_mapping = import_settings.get("mapping", {})
    if not isinstance(saved_mapping, dict) or not saved_mapping:
        return JsonResponse({"error": "Saved mapping is required before validation"}, status=400)
    task_default_field_values = build_task_default_field_values(
        session.entity_type,
        normalize_task_defaults(import_settings.get("task_defaults", {})),
    )
    try:
        saved_dedup = normalize_entity_dedup_settings(session.entity_type, import_settings.get("dedup", {}))
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    data_start_row = max(1, int(session.data_start_row or preview_data.get("data_start_row") or 1))
    total_rows = int(session.total_rows or preview_data.get("total_rows") or 0)
    if total_rows <= 0:
        try:
            total_rows = calculate_import_total_rows(session, str(selected_sheet_name), data_start_row)
        except ValueError as error:
            return JsonResponse({"error": str(error)}, status=400)
    if build_import_row_limit_payload(total_rows)["row_limit_exceeded"]:
        return build_import_row_limit_error_response(total_rows)

    try:
        fields, rows, row_numbers, preflight = load_session_preflight_context(
            account,
            session,
            columns=columns,
            selected_sheet_name=str(selected_sheet_name),
            mapping=saved_mapping,
            dedup_settings=saved_dedup,
            default_field_values=task_default_field_values,
            data_start_row=data_start_row,
        )
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    if preflight["blocking_issue_count"] > 0:
        return JsonResponse(
            {
                "error": "Resolve preflight issues before validation",
                "preflight": preflight,
            },
            status=400,
        )

    observed_values = build_observed_mapping_values(
        rows=rows,
        row_numbers=row_numbers,
        data_start_row=data_start_row,
        fields=fields,
        mapping=saved_mapping,
    )
    unmapped_values = build_unmapped_mapping_values(observed_values, saved_mapping, fields)
    unmapped_value_count = count_mapping_values(unmapped_values)
    if unmapped_value_count > 0:
        return JsonResponse(
            {
                "error": "Complete value mapping for list and status fields before validation",
                "unmapped_values": unmapped_values,
                "unmapped_value_count": unmapped_value_count,
            },
            status=400,
        )

    validation_result = build_validation_result(
        rows=rows,
        row_numbers=row_numbers,
        columns=columns,
        data_start_row=session.data_start_row,
        mapping=saved_mapping,
        fields=fields,
        account=account,
        default_field_values=task_default_field_values,
    )

    session.summary = {
        **(session.summary if isinstance(session.summary, dict) else {}),
        "preflight": preflight,
        "validation": validation_result,
    }
    session.status = ImportSession.Status.VALIDATED
    session.processed_rows = validation_result["checked_rows"]
    session.successful_rows = validation_result["valid_rows"]
    session.failed_rows = validation_result["invalid_rows"]
    session.last_error = ""
    session.save(
        update_fields=[
            "summary",
            "status",
            "processed_rows",
            "successful_rows",
            "failed_rows",
            "last_error",
            "updated_at",
        ]
    )

    return JsonResponse(
        {
            "item": {
                "session_id": str(session.id),
                "status": session.status,
                "preflight": preflight,
                **validation_result,
            }
        }
    )


def execute_import_session_dry_run_now(
    session: ImportSession,
    account,
    *,
    mode: str = DRY_RUN_MODE_PREIMPORT_SCAN,
) -> dict:
    preview_data = session.preview_data if isinstance(session.preview_data, dict) else {}
    columns = preview_data.get("columns")
    selected_sheet_name = preview_data.get("selected_sheet_name") or session.source_sheet_name
    if not isinstance(columns, list) or not columns or not selected_sheet_name:
        raise ValueError("Preview data is required before dry run")

    import_settings = session.import_settings if isinstance(session.import_settings, dict) else {}
    saved_mapping = import_settings.get("mapping", {})
    if not isinstance(saved_mapping, dict) or not saved_mapping:
        raise ValueError("Saved mapping is required before dry run")
    task_default_field_values = build_task_default_field_values(
        session.entity_type,
        normalize_task_defaults(import_settings.get("task_defaults", {})),
    )

    summary = session.summary if isinstance(session.summary, dict) else {}
    validation_summary = summary.get("validation")
    if not isinstance(validation_summary, dict):
        raise ValueError("Validation is required before dry run")

    fields = fetch_session_entity_fields(account, session)
    normalized_mode = normalize_dry_run_mode(mode)
    saved_dedup = resolve_dry_run_dedup_settings(
        session.entity_type,
        import_settings.get("dedup", {}),
        mode=normalized_mode,
    )
    summary_key = get_dry_run_summary_key(normalized_mode)
    preview_limit = None
    full_total_rows = 0
    if normalized_mode == DRY_RUN_MODE_SAMPLE_PREVIEW:
        full_row_numbers = extract_preview_rows(session, str(selected_sheet_name), preview_limit=None)[2]
        full_total_rows = sum(1 for row_number in full_row_numbers if row_number >= session.data_start_row)
        preview_limit = max(0, int(session.data_start_row or 1) - 1) + SAMPLE_PREVIEW_ROW_LIMIT
    _columns, rows, row_numbers = extract_preview_rows(session, str(selected_sheet_name), preview_limit=preview_limit)
    total_rows = sum(1 for row_number in row_numbers if row_number >= session.data_start_row)
    if normalized_mode != DRY_RUN_MODE_SAMPLE_PREVIEW:
        full_total_rows = total_rows
    session.summary = {
        **summary,
        "dry_run": None,
        summary_key: None,
        "warm_progress": None,
    }
    session.status = ImportSession.Status.RUNNING
    session.total_rows = total_rows
    session.last_error = ""
    session.processed_rows = 0
    session.successful_rows = 0
    session.failed_rows = 0
    session.save(
        update_fields=[
            "summary",
            "status",
            "total_rows",
            "last_error",
            "processed_rows",
            "successful_rows",
            "failed_rows",
            "updated_at",
        ]
    )

    def _save_progress(*, checked_rows, ready_rows, skipped_rows, pending_decision_rows):
        session.processed_rows = checked_rows
        session.successful_rows = ready_rows
        session.failed_rows = skipped_rows
        session.save(update_fields=["processed_rows", "successful_rows", "failed_rows", "updated_at"])

    def _save_warm_progress(*, done, total):
        try:
            s = session.summary if isinstance(session.summary, dict) else {}
            s = {**s, "warm_progress": {"done": done, "total": total}}
            session.summary = s
            session.save(update_fields=["summary", "updated_at"])
        except Exception:
            pass

    dry_run_result = execute_dry_run(
        account=account,
        entity_type=session.entity_type,
        rows=rows,
        row_numbers=row_numbers,
        columns=columns,
        data_start_row=session.data_start_row,
        mapping=saved_mapping,
        validation_summary=validation_summary,
        fields=fields,
        dedup_settings=saved_dedup,
        should_cancel=lambda: is_session_cancel_requested(session.id),
        default_field_values=task_default_field_values,
        progress_callback=_save_progress,
        warm_progress_callback=_save_warm_progress,
        entity_config=get_session_entity_config(session),
    )
    dry_run_result = {
        **dry_run_result,
        "mode": normalized_mode,
        "is_partial": normalized_mode == DRY_RUN_MODE_SAMPLE_PREVIEW and (full_total_rows or total_rows) > total_rows,
        "sample_limit": SAMPLE_PREVIEW_ROW_LIMIT if normalized_mode == DRY_RUN_MODE_SAMPLE_PREVIEW else None,
        "full_total_rows": full_total_rows or total_rows,
    }

    summary = session.summary if isinstance(session.summary, dict) else {}
    session.summary = {
        **summary,
        "dry_run": dry_run_result,
        summary_key: dry_run_result,
    }
    session.status = ImportSession.Status.CANCELLED if dry_run_result.get("cancelled") else ImportSession.Status.VALIDATED
    session.processed_rows = dry_run_result["checked_rows"]
    session.successful_rows = dry_run_result["ready_rows"]
    session.failed_rows = dry_run_result["skipped_rows"]
    session.last_error = ""
    session.save(
        update_fields=[
            "summary",
            "status",
            "processed_rows",
            "successful_rows",
            "failed_rows",
            "last_error",
            "updated_at",
        ]
    )

    return {
        "session_id": str(session.id),
        "status": session.status,
        **dry_run_result,
    }


@xframe_options_exempt
@csrf_exempt
@require_http_methods(["POST"])
@log_errors("import_session_dry_run")
@auth_required
def import_session_dry_run(request: AuthorizedRequest, session_id):
    account = request.bitrix24_account
    portal_member_id = getattr(account, "member_id", "")
    portal_domain = getattr(account, "domain_url", "")

    session = load_portal_session(portal_member_id, portal_domain, session_id)
    if session is None:
        return JsonResponse({"error": "Import session not found"}, status=404)
    if not can_run_session(account, session):
        return permission_denied_response()
    if has_active_import_job(session):
        return JsonResponse({"error": "Import session is already queued or running"}, status=409)

    preview_data = session.preview_data if isinstance(session.preview_data, dict) else {}
    columns = preview_data.get("columns")
    selected_sheet_name = preview_data.get("selected_sheet_name") or session.source_sheet_name
    if not isinstance(columns, list) or not columns or not selected_sheet_name:
        return JsonResponse({"error": "Preview data is required before dry run"}, status=400)

    import_settings = session.import_settings if isinstance(session.import_settings, dict) else {}
    saved_mapping = import_settings.get("mapping", {})
    if not isinstance(saved_mapping, dict) or not saved_mapping:
        return JsonResponse({"error": "Saved mapping is required before dry run"}, status=400)
    try:
        normalize_entity_dedup_settings(session.entity_type, import_settings.get("dedup", {}))
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    summary = session.summary if isinstance(session.summary, dict) else {}
    validation_summary = summary.get("validation")
    if not isinstance(validation_summary, dict):
        return JsonResponse({"error": "Validation is required before dry run"}, status=400)
    mode = normalize_dry_run_mode((request.data or {}).get("mode") if isinstance(request.data, dict) else None)
    summary_key = get_dry_run_summary_key(mode)

    if is_import_queue_enabled():
        if getattr(account, "id", None) is None:
            return JsonResponse({"error": "Queue execution requires a persisted Bitrix24 account"}, status=400)

        total_rows = sum(
            1
            for row_number in extract_preview_rows(session, str(selected_sheet_name), preview_limit=None)[2]
            if row_number >= session.data_start_row
        )
        if mode == DRY_RUN_MODE_SAMPLE_PREVIEW:
            total_rows = min(total_rows or SAMPLE_PREVIEW_ROW_LIMIT, SAMPLE_PREVIEW_ROW_LIMIT)
        session.summary = {
            **summary,
            "dry_run": None,
            summary_key: None,
        }
        session.status = ImportSession.Status.RUNNING
        session.total_rows = total_rows
        session.last_error = ""
        session.processed_rows = 0
        session.successful_rows = 0
        session.failed_rows = 0
        session.save(
            update_fields=[
                "summary",
                "status",
                "total_rows",
                "last_error",
                "processed_rows",
                "successful_rows",
                "failed_rows",
                "updated_at",
            ]
        )
        try:
            enqueue_import_session_dry_run(session, account, mode=mode)
        except KombuOperationalError as error:
            logging.warning("Import queue is unavailable, falling back to synchronous dry run: %s", error)
        else:
            session.refresh_from_db()
            return JsonResponse({"item": serialize_session_response_item(session)}, status=202)

    try:
        dry_run_item = execute_import_session_dry_run_now(session=session, account=account, mode=mode)
    except Exception as error:
        return JsonResponse({"error": safe_format_import_error(error)}, status=400)

    return JsonResponse(
        {
            "item": dry_run_item
        }
    )


def execute_import_session_run_now(session: ImportSession, account, *, per_row_decisions: dict | None = None) -> dict:
    preview_data = session.preview_data if isinstance(session.preview_data, dict) else {}
    columns = preview_data.get("columns")
    selected_sheet_name = preview_data.get("selected_sheet_name") or session.source_sheet_name
    if not isinstance(columns, list) or not columns or not selected_sheet_name:
        raise ValueError("Preview data is required before import execution")

    import_settings = session.import_settings if isinstance(session.import_settings, dict) else {}
    saved_mapping = import_settings.get("mapping", {})
    if not isinstance(saved_mapping, dict) or not saved_mapping:
        raise ValueError("Saved mapping is required before import execution")
    task_default_field_values = build_task_default_field_values(
        session.entity_type,
        normalize_task_defaults(import_settings.get("task_defaults", {})),
    )
    saved_dedup = normalize_entity_dedup_settings(session.entity_type, import_settings.get("dedup", {}))

    normalized_per_row_decisions = per_row_decisions or normalize_per_row_decisions(import_settings.get("per_row_decisions"))

    summary = session.summary if isinstance(session.summary, dict) else {}
    validation_summary = summary.get("validation")
    preimport_scan_summary = get_preimport_scan_summary(summary)
    if not isinstance(validation_summary, dict):
        raise ValueError("Validation is required before import execution")
    missing_pending_decision_rows = get_missing_pending_decision_rows(
        saved_dedup,
        summary,
        normalized_per_row_decisions,
    )
    if missing_pending_decision_rows is None or missing_pending_decision_rows:
        raise ValueError("Run a dry run and choose an action for each duplicate before import execution")

    summary = session.summary if isinstance(session.summary, dict) else {}
    session.summary = {**summary, "warm_progress": None}
    session.status = ImportSession.Status.RUNNING
    session.last_error = ""
    session.processed_rows = 0
    session.successful_rows = 0
    session.failed_rows = 0
    session.save(update_fields=["summary", "status", "last_error", "processed_rows", "successful_rows", "failed_rows", "updated_at"])

    def _save_warm_progress_import(*, done, total):
        try:
            s = session.summary if isinstance(session.summary, dict) else {}
            s = {**s, "warm_progress": {"done": done, "total": total}}
            session.summary = s
            session.save(update_fields=["summary", "updated_at"])
        except Exception:
            pass

    try:
        fields, rows, row_numbers, preflight = load_session_preflight_context(
            account,
            session,
            columns=columns,
            selected_sheet_name=str(selected_sheet_name),
            mapping=saved_mapping,
            dedup_settings=saved_dedup,
            default_field_values=task_default_field_values,
            data_start_row=max(1, int(session.data_start_row or preview_data.get("data_start_row") or 1)),
        )
        if preflight["blocking_issue_count"] > 0:
            raise ValueError("Resolve preflight issues before import execution")

        session.total_rows = sum(1 for rn in row_numbers if rn >= session.data_start_row)
        if session.total_rows > MAX_IMPORT_ROWS:
            raise ValueError(
                f"Файл содержит слишком много строк данных ({session.total_rows:,}). "
                f"Максимум: {MAX_IMPORT_ROWS:,} строк за один импорт."
            )
        create_phase_row_numbers, duplicate_phase_row_numbers = collect_preimport_scan_stage_row_numbers(preimport_scan_summary)
        if not create_phase_row_numbers and not duplicate_phase_row_numbers:
            create_phase_row_numbers = [rn for rn in row_numbers if rn >= session.data_start_row]

        create_phase_rows, create_phase_row_numbers = filter_rows_by_row_numbers(rows, row_numbers, create_phase_row_numbers)
        duplicate_phase_rows, duplicate_phase_row_numbers = filter_rows_by_row_numbers(rows, row_numbers, duplicate_phase_row_numbers)
        create_phase_total = len(create_phase_row_numbers)
        duplicate_phase_total = len(duplicate_phase_row_numbers)

        store_import_phase_progress(
            session,
            create_phase_total=create_phase_total,
            duplicate_phase_total=duplicate_phase_total,
            create_phase_processed=0,
            duplicate_phase_processed=0,
            active_phase="new_records" if create_phase_total > 0 else "duplicates",
        )
        session.save(update_fields=["summary", "total_rows", "updated_at"])

        create_phase_progress = {
            "checked_rows": 0,
            "created_rows": 0,
            "updated_rows": 0,
            "failed_rows": 0,
        }

        def _save_create_phase_progress(*, checked_rows, created_rows, updated_rows, failed_rows):
            create_phase_progress["checked_rows"] = checked_rows
            create_phase_progress["created_rows"] = created_rows
            create_phase_progress["updated_rows"] = updated_rows
            create_phase_progress["failed_rows"] = failed_rows
            session.processed_rows = checked_rows
            session.successful_rows = created_rows + updated_rows
            session.failed_rows = failed_rows
            store_import_phase_progress(
                session,
                create_phase_total=create_phase_total,
                duplicate_phase_total=duplicate_phase_total,
                create_phase_processed=checked_rows,
                duplicate_phase_processed=0,
                active_phase="new_records",
            )
            session.save(update_fields=["summary", "processed_rows", "successful_rows", "failed_rows", "updated_at"])

        def _on_rate_limit_pause(wait_seconds):
            import time as _t
            try:
                summary = session.summary if isinstance(session.summary, dict) else {}
                progress = summary.get("import_progress") if isinstance(summary.get("import_progress"), dict) else {}
                progress["pause_info"] = {
                    "wait_seconds": int(wait_seconds),
                    "resume_at": int(_t.time()) + int(wait_seconds),
                }
                summary["import_progress"] = progress
                session.summary = summary
                session.save(update_fields=["summary", "updated_at"])
            except Exception:
                pass

        def _on_rate_limit_resume():
            try:
                summary = session.summary if isinstance(session.summary, dict) else {}
                progress = summary.get("import_progress") if isinstance(summary.get("import_progress"), dict) else {}
                progress.pop("pause_info", None)
                summary["import_progress"] = progress
                session.summary = summary
                session.save(update_fields=["summary", "updated_at"])
            except Exception:
                pass

        create_phase_result = execute_import(
            account=account,
            entity_type=session.entity_type,
            rows=create_phase_rows,
            row_numbers=create_phase_row_numbers,
            columns=columns,
            data_start_row=session.data_start_row,
            mapping=saved_mapping,
            validation_summary=validation_summary,
            fields=fields,
            dedup_settings=saved_dedup,
            should_cancel=lambda: is_session_cancel_requested(session.id),
            default_field_values=task_default_field_values,
            per_row_decisions=normalized_per_row_decisions,
            progress_callback=_save_create_phase_progress,
            warm_progress_callback=_save_warm_progress_import,
            entity_config=get_session_entity_config(session),
            on_rate_limit_pause=_on_rate_limit_pause,
            on_rate_limit_resume=_on_rate_limit_resume,
        )
        _save_create_phase_progress(
            checked_rows=create_phase_result["checked_rows"],
            created_rows=create_phase_result["created_rows"],
            updated_rows=create_phase_result.get("updated_rows", 0),
            failed_rows=create_phase_result["failed_rows"],
        )

        duplicate_phase_result = {
            "checked_rows": 0,
            "created_rows": 0,
            "updated_rows": 0,
            "failed_rows": 0,
            "skipped_rows": 0,
            "cancelled": False,
            "cancelled_rows": 0,
            "remaining_rows": 0,
            "created_ids": [],
            "updated_ids": [],
            "results": [],
            "auth_error": "",
            "fatal_error": "",
        }

        if not create_phase_result.get("cancelled") and duplicate_phase_total > 0:
            def _save_duplicate_phase_progress(*, checked_rows, created_rows, updated_rows, failed_rows):
                session.processed_rows = create_phase_result["checked_rows"] + checked_rows
                session.successful_rows = (
                    create_phase_result["created_rows"]
                    + create_phase_result.get("updated_rows", 0)
                    + created_rows
                    + updated_rows
                )
                session.failed_rows = create_phase_result["failed_rows"] + failed_rows
                store_import_phase_progress(
                    session,
                    create_phase_total=create_phase_total,
                    duplicate_phase_total=duplicate_phase_total,
                    create_phase_processed=create_phase_result["checked_rows"],
                    duplicate_phase_processed=checked_rows,
                    active_phase="duplicates",
                )
                session.save(update_fields=["summary", "processed_rows", "successful_rows", "failed_rows", "updated_at"])

            duplicate_phase_result = execute_import(
                account=account,
                entity_type=session.entity_type,
                rows=duplicate_phase_rows,
                row_numbers=duplicate_phase_row_numbers,
                columns=columns,
                data_start_row=session.data_start_row,
                mapping=saved_mapping,
                validation_summary=validation_summary,
                fields=fields,
                dedup_settings=saved_dedup,
                should_cancel=lambda: is_session_cancel_requested(session.id),
                default_field_values=task_default_field_values,
                per_row_decisions=normalized_per_row_decisions,
                progress_callback=_save_duplicate_phase_progress,
                entity_config=get_session_entity_config(session),
                on_rate_limit_pause=_on_rate_limit_pause,
                on_rate_limit_resume=_on_rate_limit_resume,
                warm_progress_callback=_save_warm_progress_import,
            )
            _save_duplicate_phase_progress(
                checked_rows=duplicate_phase_result["checked_rows"],
                created_rows=duplicate_phase_result["created_rows"],
                updated_rows=duplicate_phase_result.get("updated_rows", 0),
                failed_rows=duplicate_phase_result["failed_rows"],
            )

        import_result = merge_import_execution_results(create_phase_result, duplicate_phase_result)
        import_result["auth_error"] = str(create_phase_result.get("auth_error") or duplicate_phase_result.get("auth_error") or "")
        import_result["fatal_error"] = str(create_phase_result.get("fatal_error") or duplicate_phase_result.get("fatal_error") or "")
    except Exception as error:
        session.status = ImportSession.Status.FAILED
        session.last_error = safe_format_import_error(error)
        session.save(update_fields=["status", "last_error", "updated_at"])
        raise

    store_import_phase_progress(
        session,
        create_phase_total=create_phase_total,
        duplicate_phase_total=duplicate_phase_total,
        create_phase_processed=create_phase_result["checked_rows"],
        duplicate_phase_processed=duplicate_phase_result["checked_rows"],
        active_phase="completed",
    )

    session.summary = {
        **summary,
        "import_run": import_result,
        "import_progress": (session.summary if isinstance(session.summary, dict) else {}).get("import_progress"),
    }
    terminal_error = str(import_result.get("fatal_error") or import_result.get("auth_error") or "")
    session.status = ImportSession.Status.CANCELLED if import_result.get("cancelled") else ImportSession.Status.COMPLETED
    session.processed_rows = import_result["checked_rows"]
    session.successful_rows = import_result["created_rows"] + import_result.get("updated_rows", 0)
    session.failed_rows = import_result["failed_rows"]
    session.last_error = terminal_error
    session.save(
        update_fields=[
            "summary",
            "status",
            "processed_rows",
            "successful_rows",
            "failed_rows",
            "last_error",
            "updated_at",
        ]
    )

    return {
        "session_id": str(session.id),
        "status": session.status,
        **import_result,
    }

@xframe_options_exempt
@csrf_exempt
@require_http_methods(["POST"])
@log_errors("import_session_run")
@auth_required
def import_session_run(request: AuthorizedRequest, session_id):
    account = request.bitrix24_account
    portal_member_id = getattr(account, "member_id", "")
    portal_domain = getattr(account, "domain_url", "")

    session = load_portal_session(portal_member_id, portal_domain, session_id)
    if session is None:
        return JsonResponse({"error": "Import session not found"}, status=404)
    if not can_run_session(account, session):
        return permission_denied_response()
    if has_active_import_job(session):
        return JsonResponse({"error": "Import session is already queued or running"}, status=409)

    preview_data = session.preview_data if isinstance(session.preview_data, dict) else {}
    columns = preview_data.get("columns")
    selected_sheet_name = preview_data.get("selected_sheet_name") or session.source_sheet_name
    if not isinstance(columns, list) or not columns or not selected_sheet_name:
        return JsonResponse({"error": "Preview data is required before import execution"}, status=400)

    import_settings = session.import_settings if isinstance(session.import_settings, dict) else {}
    saved_mapping = import_settings.get("mapping", {})
    if not isinstance(saved_mapping, dict) or not saved_mapping:
        return JsonResponse({"error": "Saved mapping is required before import execution"}, status=400)
    task_default_field_values = build_task_default_field_values(
        session.entity_type,
        normalize_task_defaults(import_settings.get("task_defaults", {})),
    )
    try:
        saved_dedup = normalize_entity_dedup_settings(session.entity_type, import_settings.get("dedup", {}))
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    per_row_decisions = normalize_per_row_decisions(
        (request.data or {}).get("per_row_decisions") if isinstance(request.data, dict) else None
    ) or normalize_per_row_decisions(import_settings.get("per_row_decisions"))

    summary = session.summary if isinstance(session.summary, dict) else {}
    missing_pending_decision_rows = get_missing_pending_decision_rows(saved_dedup, summary, per_row_decisions)
    if missing_pending_decision_rows is None or missing_pending_decision_rows:
        response_payload = {
            "error": "Run a dry run and choose an action for each duplicate before import execution",
        }
        if missing_pending_decision_rows:
            response_payload["pending_decision_rows"] = missing_pending_decision_rows
        return JsonResponse(response_payload, status=400)

    if per_row_decisions:
        import_settings = {**import_settings, "per_row_decisions": per_row_decisions}
        session.import_settings = import_settings
        session.save(update_fields=["import_settings", "updated_at"])

    validation_summary = summary.get("validation")
    if not isinstance(validation_summary, dict):
        return JsonResponse({"error": "Validation is required before import execution"}, status=400)

    data_start_row = max(1, int(session.data_start_row or preview_data.get("data_start_row") or 1))
    try:
        _fields, _rows, _row_numbers, preflight = load_session_preflight_context(
            account,
            session,
            columns=columns,
            selected_sheet_name=str(selected_sheet_name),
            mapping=saved_mapping,
            dedup_settings=saved_dedup,
            default_field_values=task_default_field_values,
            data_start_row=data_start_row,
        )
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    if preflight["blocking_issue_count"] > 0:
        return JsonResponse(
            {
                "error": "Resolve preflight issues before import execution",
                "preflight": preflight,
            },
            status=400,
        )

    if is_import_queue_enabled():
        if getattr(account, "id", None) is None:
            return JsonResponse({"error": "Queue execution requires a persisted Bitrix24 account"}, status=400)

        session.status = ImportSession.Status.RUNNING
        session.last_error = ""
        session.processed_rows = 0
        session.successful_rows = 0
        session.failed_rows = 0
        session.save(
            update_fields=["status", "last_error", "processed_rows", "successful_rows", "failed_rows", "updated_at"]
        )
        try:
            enqueue_import_session_run(session, account, per_row_decisions=per_row_decisions)
        except KombuOperationalError as error:
            logging.warning("Import queue is unavailable, falling back to synchronous run: %s", error)
        else:
            session.refresh_from_db()
            return JsonResponse({"item": serialize_session_response_item(session)}, status=202)

    try:
        import_item = execute_import_session_run_now(
            session=session,
            account=account,
            per_row_decisions=per_row_decisions,
        )
    except Exception as error:
        return JsonResponse({"error": safe_format_import_error(error)}, status=400)

    return JsonResponse({"item": import_item})


@xframe_options_exempt
@csrf_exempt
@require_http_methods(["POST"])
@log_errors("import_session_cancel")
@auth_required
def import_session_cancel(request: AuthorizedRequest, session_id):
    account = request.bitrix24_account
    portal_member_id = getattr(account, "member_id", "")
    portal_domain = getattr(account, "domain_url", "")

    session = load_portal_session(portal_member_id, portal_domain, session_id)
    if session is None:
        return JsonResponse({"error": "Import session not found"}, status=404)
    if not can_cancel_session(account, session):
        return permission_denied_response()
    if session.status != ImportSession.Status.RUNNING:
        return JsonResponse({"error": "Only running import can be cancelled"}, status=400)

    from .services.background_jobs import _update_session_job_state

    session.status = ImportSession.Status.CANCELLED
    session.last_error = ""
    summary = session.summary if isinstance(session.summary, dict) else {}
    job = summary.get("job") if isinstance(summary.get("job"), dict) else {}
    job_mode = str(job.get("mode") or "run").strip() or "run"
    _update_session_job_state(session, mode=job_mode, state="cancelled")
    session.save(update_fields=["status", "last_error", "summary", "updated_at"])
    return JsonResponse({"item": serialize_session(session)})


@xframe_options_exempt
@require_GET
@log_errors("import_session_report_csv")
@auth_required
def import_session_report_csv(request: AuthorizedRequest, session_id):
    account = request.bitrix24_account
    portal_member_id = getattr(account, "member_id", "")
    portal_domain = getattr(account, "domain_url", "")

    session = load_portal_session(portal_member_id, portal_domain, session_id)
    if session is None:
        return JsonResponse({"error": "Import session not found"}, status=404)
    if not can_view_session(account, session) or not has_permission(account, "reports.view"):
        return permission_denied_response()

    summary = session.summary if isinstance(session.summary, dict) else {}
    import_run = summary.get("import_run")
    if not isinstance(import_run, dict) or not isinstance(import_run.get("results"), list):
        return JsonResponse({"error": "Import results are required before report download"}, status=400)

    response = HttpResponse(
        build_import_report_csv(import_run),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{build_import_report_filename(session.original_filename)}"'
    return response


def execute_import_session_retry_now(session: ImportSession, account) -> dict:
    preview_data = session.preview_data if isinstance(session.preview_data, dict) else {}
    columns = preview_data.get("columns")
    selected_sheet_name = preview_data.get("selected_sheet_name") or session.source_sheet_name
    if not isinstance(columns, list) or not columns or not selected_sheet_name:
        raise ValueError("Preview data is required before retry")

    import_settings = session.import_settings if isinstance(session.import_settings, dict) else {}
    saved_mapping = import_settings.get("mapping", {})
    if not isinstance(saved_mapping, dict) or not saved_mapping:
        raise ValueError("Saved mapping is required before retry")
    task_default_field_values = build_task_default_field_values(
        session.entity_type,
        normalize_task_defaults(import_settings.get("task_defaults", {})),
    )
    saved_dedup = normalize_entity_dedup_settings(session.entity_type, import_settings.get("dedup", {}))

    summary = session.summary if isinstance(session.summary, dict) else {}
    previous_import_run = summary.get("import_run")
    if not isinstance(previous_import_run, dict) or not isinstance(previous_import_run.get("results"), list):
        raise ValueError("Import results are required before retry")

    retry_row_numbers = collect_retryable_row_numbers(previous_import_run.get("results", []))
    if not retry_row_numbers:
        raise ValueError("There are no failed rows to retry")

    session.status = ImportSession.Status.RUNNING
    session.last_error = ""
    session.total_rows = len(retry_row_numbers)
    session.processed_rows = 0
    session.successful_rows = 0
    session.failed_rows = 0
    session.save(update_fields=["status", "last_error", "total_rows", "processed_rows", "successful_rows", "failed_rows", "updated_at"])

    def _save_progress(*, checked_rows, created_rows, updated_rows, failed_rows):
        session.processed_rows = checked_rows
        session.successful_rows = created_rows + updated_rows
        session.failed_rows = failed_rows
        session.save(update_fields=["processed_rows", "successful_rows", "failed_rows", "updated_at"])

    def _on_retry_rate_limit_pause(wait_seconds):
        import time as _t
        try:
            summary = session.summary if isinstance(session.summary, dict) else {}
            progress = summary.get("import_progress") if isinstance(summary.get("import_progress"), dict) else {}
            progress["pause_info"] = {
                "wait_seconds": int(wait_seconds),
                "resume_at": int(_t.time()) + int(wait_seconds),
            }
            summary["import_progress"] = progress
            session.summary = summary
            session.save(update_fields=["summary", "updated_at"])
        except Exception:
            pass

    def _on_retry_rate_limit_resume():
        try:
            summary = session.summary if isinstance(session.summary, dict) else {}
            progress = summary.get("import_progress") if isinstance(summary.get("import_progress"), dict) else {}
            progress.pop("pause_info", None)
            summary["import_progress"] = progress
            session.summary = summary
            session.save(update_fields=["summary", "updated_at"])
        except Exception:
            pass

    try:
        fields = fetch_session_entity_fields(account, session)
        _columns, rows, row_numbers = extract_preview_rows(session, str(selected_sheet_name), preview_limit=None)
        validation_result = build_validation_result(
            rows=rows,
            row_numbers=row_numbers,
            columns=columns,
            data_start_row=session.data_start_row,
            mapping=saved_mapping,
            fields=fields,
            account=account,
            default_field_values=task_default_field_values,
        )
        retry_rows, retry_row_numbers_filtered = filter_rows_by_row_numbers(rows, row_numbers, retry_row_numbers)
        retry_result = execute_import(
            account=account,
            entity_type=session.entity_type,
            rows=retry_rows,
            row_numbers=retry_row_numbers_filtered,
            columns=columns,
            data_start_row=session.data_start_row,
            mapping=saved_mapping,
            validation_summary=validation_result,
            fields=fields,
            dedup_settings=saved_dedup,
            should_cancel=lambda: is_session_cancel_requested(session.id),
            default_field_values=task_default_field_values,
            per_row_decisions=normalize_per_row_decisions(import_settings.get("per_row_decisions")),
            progress_callback=_save_progress,
            entity_config=get_session_entity_config(session),
            on_rate_limit_pause=_on_retry_rate_limit_pause,
            on_rate_limit_resume=_on_retry_rate_limit_resume,
        )
    except Exception as error:
        session.status = ImportSession.Status.FAILED
        session.last_error = safe_format_import_error(error)
        session.save(update_fields=["status", "last_error", "updated_at"])
        raise

    retry_runs = summary.get("retry_runs", [])
    if not isinstance(retry_runs, list):
        retry_runs = []
    retry_runs = [*retry_runs, retry_result]
    merged_import_run = merge_import_run_results(previous_import_run, retry_result)

    session.summary = {
        **summary,
        "validation": validation_result,
        "import_run": merged_import_run,
        "retry_runs": retry_runs,
    }
    session.status = ImportSession.Status.CANCELLED if retry_result.get("cancelled") else ImportSession.Status.COMPLETED
    session.processed_rows = merged_import_run["checked_rows"]
    session.successful_rows = merged_import_run["created_rows"] + merged_import_run.get("updated_rows", 0)
    session.failed_rows = merged_import_run["failed_rows"]
    session.last_error = str(retry_result.get("fatal_error") or retry_result.get("auth_error") or "")
    session.save(
        update_fields=[
            "summary",
            "status",
            "processed_rows",
            "successful_rows",
            "failed_rows",
            "last_error",
            "updated_at",
        ]
    )

    return {
        "session_id": str(session.id),
        "status": session.status,
        "retried_rows": len(retry_row_numbers_filtered),
        "retry_result": retry_result,
        **merged_import_run,
    }

@xframe_options_exempt
@csrf_exempt
@require_http_methods(["POST"])
@log_errors("import_session_retry_failed")
@auth_required
def import_session_retry_failed(request: AuthorizedRequest, session_id):
    account = request.bitrix24_account
    portal_member_id = getattr(account, "member_id", "")
    portal_domain = getattr(account, "domain_url", "")

    session = load_portal_session(portal_member_id, portal_domain, session_id)
    if session is None:
        return JsonResponse({"error": "Import session not found"}, status=404)
    if not can_run_session(account, session):
        return permission_denied_response()
    if has_active_import_job(session):
        return JsonResponse({"error": "Import session is already queued or running"}, status=409)

    preview_data = session.preview_data if isinstance(session.preview_data, dict) else {}
    columns = preview_data.get("columns")
    selected_sheet_name = preview_data.get("selected_sheet_name") or session.source_sheet_name
    if not isinstance(columns, list) or not columns or not selected_sheet_name:
        return JsonResponse({"error": "Preview data is required before retry"}, status=400)

    import_settings = session.import_settings if isinstance(session.import_settings, dict) else {}
    saved_mapping = import_settings.get("mapping", {})
    if not isinstance(saved_mapping, dict) or not saved_mapping:
        return JsonResponse({"error": "Saved mapping is required before retry"}, status=400)
    task_default_field_values = build_task_default_field_values(
        session.entity_type,
        normalize_task_defaults(import_settings.get("task_defaults", {})),
    )
    try:
        saved_dedup = normalize_entity_dedup_settings(session.entity_type, import_settings.get("dedup", {}))
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    summary = session.summary if isinstance(session.summary, dict) else {}
    previous_import_run = summary.get("import_run")
    if not isinstance(previous_import_run, dict) or not isinstance(previous_import_run.get("results"), list):
        return JsonResponse({"error": "Import results are required before retry"}, status=400)

    retry_row_numbers = collect_retryable_row_numbers(previous_import_run.get("results", []))
    if not retry_row_numbers:
        return JsonResponse({"error": "There are no failed rows to retry"}, status=400)

    if is_import_queue_enabled():
        if getattr(account, "id", None) is None:
            return JsonResponse({"error": "Queue execution requires a persisted Bitrix24 account"}, status=400)

        session.status = ImportSession.Status.RUNNING
        session.last_error = ""
        session.processed_rows = 0
        session.successful_rows = 0
        session.failed_rows = 0
        session.total_rows = len(retry_row_numbers)
        summary = session.summary if isinstance(session.summary, dict) else {}
        session.summary = {**summary, "retry_total_rows": len(retry_row_numbers)}
        session.save(
            update_fields=["status", "last_error", "processed_rows", "successful_rows", "failed_rows", "total_rows", "summary", "updated_at"]
        )
        try:
            enqueue_import_session_retry(session, account)
        except KombuOperationalError as error:
            logging.warning("Import retry queue is unavailable, falling back to synchronous retry: %s", error)
        else:
            session.refresh_from_db()
            return JsonResponse({"item": serialize_session_response_item(session)}, status=202)

    try:
        retry_item = execute_import_session_retry_now(session=session, account=account)
    except Exception as error:
        return JsonResponse({"error": safe_format_import_error(error)}, status=400)

    return JsonResponse({"item": retry_item})


@xframe_options_exempt
@csrf_exempt
@require_http_methods(["POST"])
@log_errors("import_session_upload")
@auth_required
def import_session_upload(request: AuthorizedRequest, session_id):
    account = request.bitrix24_account
    portal_member_id = getattr(account, "member_id", "")
    portal_domain = getattr(account, "domain_url", "")

    session = load_portal_session(portal_member_id, portal_domain, session_id)
    if session is None:
        return JsonResponse({"error": "Import session not found"}, status=404)
    if not can_edit_session(account, session):
        return permission_denied_response()

    upload = request.FILES.get("file")
    if upload is None:
        return JsonResponse({"error": "File is required"}, status=400)
    if int(getattr(upload, "size", 0) or 0) > get_max_import_file_size_bytes():
        return JsonResponse(
            {"error": f"Файл слишком большой. Максимум для импорта — {get_max_import_file_size_megabytes()} МБ."},
            status=400,
        )

    try:
        safe_filename = _validate_and_sanitize_upload(upload)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    session.stored_file.save(safe_filename, upload, save=False)
    session.original_filename = safe_filename
    session.file_size_bytes = upload.size
    session.status = ImportSession.Status.UPLOADED
    session.last_error = ""
    session.save(
        update_fields=[
            "stored_file",
            "original_filename",
            "file_size_bytes",
            "status",
            "last_error",
            "updated_at",
        ]
    )

    return JsonResponse({"item": serialize_session(session)})


@xframe_options_exempt
@csrf_exempt
@require_http_methods(["GET", "PATCH"])
@log_errors("import_session_preview")
@auth_required
def import_session_preview(request: AuthorizedRequest, session_id):
    account = request.bitrix24_account
    portal_member_id = getattr(account, "member_id", "")
    portal_domain = getattr(account, "domain_url", "")

    session = load_portal_session(portal_member_id, portal_domain, session_id)
    if session is None:
        return JsonResponse({"error": "Import session not found"}, status=404)
    if request.method == "GET":
        if not can_view_session(account, session):
            return permission_denied_response()
    elif not can_edit_session(account, session):
        return permission_denied_response()

    try:
        sheet_names = extract_sheet_names(session)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    requested_sheet_name = (request.data or {}).get("sheet_name")
    selected_sheet_name = requested_sheet_name or session.source_sheet_name or sheet_names[0]
    if selected_sheet_name not in sheet_names:
        return JsonResponse({"error": "Selected sheet does not exist"}, status=400)

    try:
        columns, preview_rows, row_numbers, preview_meta = extract_preview_rows_with_meta(session, selected_sheet_name)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    structure = detect_preview_structure(columns, preview_rows, row_numbers)
    if request.method == "PATCH":
        try:
            structure = apply_preview_structure_overrides(
                columns,
                preview_rows,
                row_numbers,
                structure,
                request.data or {},
            )
        except ValueError as error:
            return JsonResponse({"error": str(error)}, status=400)

    try:
        total_rows = calculate_import_total_rows(
            session,
            str(selected_sheet_name),
            int(structure["data_start_row"] or 1),
        )
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    row_limit = build_import_row_limit_payload(total_rows)

    session.source_sheet_name = selected_sheet_name
    session.header_row = structure["header_row"]
    session.data_start_row = structure["data_start_row"]
    session.total_rows = total_rows
    session.preview_data = {
        "sheet_names": sheet_names,
        "selected_sheet_name": selected_sheet_name,
        "columns": columns,
        "preview_rows": preview_rows,
        "header_row": structure["header_row"],
        "data_start_row": structure["data_start_row"],
        "headers": structure["headers"],
        **row_limit,
        **({} if not preview_meta else {"csv_delimiter": preview_meta.get("csv_delimiter")}),
    }
    session.last_error = ""
    session.save(
        update_fields=[
            "source_sheet_name",
            "header_row",
            "data_start_row",
            "total_rows",
            "preview_data",
            "last_error",
            "updated_at",
        ]
    )

    response_item = {
        "session_id": str(session.id),
        "sheet_names": sheet_names,
        "selected_sheet_name": selected_sheet_name,
        "columns": columns,
        "preview_rows": preview_rows,
        "header_row": structure["header_row"],
        "data_start_row": structure["data_start_row"],
        "headers": structure["headers"],
        **row_limit,
    }
    if preview_meta.get("csv_delimiter"):
        response_item["csv_delimiter"] = preview_meta["csv_delimiter"]

    return JsonResponse({"item": response_item})


@xframe_options_exempt
@require_GET
@log_errors("import_permissions_me")
@auth_required
def import_permissions_me(request: AuthorizedRequest):
    return JsonResponse({"item": build_permissions_payload(request.bitrix24_account)})


@xframe_options_exempt
@csrf_exempt
@require_http_methods(["GET", "POST"])
@log_errors("import_roles")
@auth_required
def import_roles(request: AuthorizedRequest):
    account = request.bitrix24_account
    portal_member_id = getattr(account, "member_id", "")
    portal_domain = getattr(account, "domain_url", "")

    if not has_permission(account, "roles.manage"):
        return permission_denied_response()

    if request.method == "GET":
        items = ImporterUserRole.objects.filter(
            portal_member_id=portal_member_id,
            portal_domain=portal_domain,
        ).order_by("b24_user_id")
        return JsonResponse({"items": [serialize_user_role(item) for item in items]})

    payload = request.data or {}

    try:
        b24_user_id = int(payload.get("b24_user_id"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "b24_user_id must be an integer"}, status=400)

    try:
        role = normalize_assignable_role(payload.get("role"))
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    role_item, _created = ImporterUserRole.objects.update_or_create(
        portal_member_id=portal_member_id,
        b24_user_id=b24_user_id,
        defaults={
            "portal_domain": portal_domain,
            "role": role,
            "granted_by_b24_user_id": int(getattr(account, "b24_user_id", 0) or 0),
        },
    )

    return JsonResponse({"item": serialize_user_role(role_item)})


@xframe_options_exempt
@csrf_exempt
@require_http_methods(["POST"])
@log_errors("crm_entity_fields")
@auth_required
def crm_entity_fields(request: AuthorizedRequest):
    from .services.b24_fields import fetch_entity_fields

    account = request.bitrix24_account
    if not has_permission(account, "sessions.create"):
        return permission_denied_response()

    import json
    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    entity_type = str(payload.get("entity_type") or "").strip()
    if entity_type.startswith("crm_files_"):
        entity_type = entity_type[len("crm_files_"):]

    if entity_type not in {"lead", "contact", "company", "deal"}:
        return JsonResponse({"error": f"Unsupported entity type: {entity_type}"}, status=400)

    try:
        fields = fetch_entity_fields(account, entity_type)
    except Exception as error:
        return JsonResponse({"error": str(error)}, status=500)

    return JsonResponse({
        "fields": [
            {
                "id": f["id"],
                "title": f["title"],
                "type": str(f.get("type") or "string"),
                "items": [
                    {"value": str(item.get("id") or ""), "label": str(item.get("title") or "")}
                    for item in (f.get("items") or [])
                    if item and item.get("id")
                ],
            }
            for f in fields
        ]
    })


@xframe_options_exempt
@csrf_exempt
@require_http_methods(["POST"])
@log_errors("crm_file_fields")
@auth_required
def crm_file_fields(request: AuthorizedRequest):
    from .services.b24_fields import fetch_entity_fields

    account = request.bitrix24_account
    if not has_permission(account, "sessions.create"):
        return permission_denied_response()

    import json
    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    entity_type = str(payload.get("entity_type") or "").strip()
    if entity_type.startswith("crm_files_"):
        entity_type = entity_type[len("crm_files_"):]

    if entity_type not in {"lead", "contact", "company", "deal"}:
        return JsonResponse({"error": f"Unsupported entity type: {entity_type}"}, status=400)

    try:
        fields = fetch_entity_fields(account, entity_type)
    except Exception as error:
        return JsonResponse({"error": str(error)}, status=500)

    file_fields = [
        {"id": f["id"], "title": f["title"]}
        for f in fields
        if str(f.get("type") or "").lower() in ("file", "disk_file")
    ]

    return JsonResponse({"fields": file_fields})


@xframe_options_exempt
@csrf_exempt
@require_http_methods(["POST"])
@log_errors("crm_filter_preview")
@auth_required
def crm_filter_preview(request: AuthorizedRequest):
    from .services.bulk_attach import fetch_crm_entities_page, SUPPORTED_ENTITY_TYPES, _extract_entity_title
    sample_limit = 5

    account = request.bitrix24_account
    if not has_permission(account, "sessions.create"):
        return permission_denied_response()

    import json
    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    entity_type = str(payload.get("entity_type") or "").strip()
    is_task_preview = entity_type == "task"
    if entity_type not in SUPPORTED_ENTITY_TYPES and not is_task_preview:
        return JsonResponse({"error": f"Unsupported entity type: {entity_type}"}, status=400)

    filter_params = payload.get("filter") or {}
    if not isinstance(filter_params, dict):
        filter_params = {}

    try:
        if is_task_preview:
            from .services.task_bulk_attach import fetch_task_entities_page
            page = fetch_task_entities_page(account, filter_params, start=0)
        else:
            page = fetch_crm_entities_page(account, entity_type, filter_params, start=0)
    except Exception as error:
        return JsonResponse({"error": str(error)}, status=500)

    sample = []
    for item in page["items"][:sample_limit]:
        if isinstance(item, dict):
            raw_id = item.get("ID") or item.get("id")
            sample.append({
                "id": int(raw_id) if raw_id is not None else None,
                "title": (
                    str(item.get("title") or item.get("TITLE") or raw_id or "").strip()
                    if is_task_preview
                    else _extract_entity_title(entity_type, item)
                ),
            })

    return JsonResponse({
        "total": page["total"],
        "has_more": page["next"] is not None,
        "sample": sample,
    })


@xframe_options_exempt
@csrf_exempt
@require_http_methods(["POST"])
@log_errors("bulk_attach_upload")
@auth_required
def bulk_attach_upload(request: AuthorizedRequest):
    import uuid

    account = request.bitrix24_account
    if not has_permission(account, "sessions.create"):
        return permission_denied_response()

    upload = request.FILES.get("file")
    if upload is None:
        return JsonResponse({"error": "File is required"}, status=400)

    file_id = str(uuid.uuid4())
    upload_dir = os.path.join(settings.MEDIA_ROOT, "bulk-attach-uploads", file_id)
    os.makedirs(upload_dir, exist_ok=True)

    raw_name = getattr(upload, "name", None) or "attachment.bin"
    safe_name = re.sub(r"[^\w.\-]", "_", raw_name)[:200] or "attachment.bin"

    with open(os.path.join(upload_dir, safe_name), "wb") as f:
        for chunk in upload.chunks():
            f.write(chunk)

    return JsonResponse({"file_id": file_id, "file_name": safe_name})


@xframe_options_exempt
@csrf_exempt
@require_http_methods(["POST"])
@log_errors("bulk_attach_session_create")
@auth_required
def bulk_attach_session_create(request: AuthorizedRequest):
    account = request.bitrix24_account
    if not has_permission(account, "sessions.create"):
        return permission_denied_response()

    import json
    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    from .services.bulk_attach import SUPPORTED_ENTITY_TYPES, CRM_FILES_ENTITY_TYPES

    entity_type = str(payload.get("entity_type") or "").strip()
    is_task_bulk_attach = entity_type == "task"
    if entity_type not in SUPPORTED_ENTITY_TYPES and not is_task_bulk_attach:
        return JsonResponse({"error": f"Unsupported entity type: {entity_type}"}, status=400)

    file_url = str(payload.get("file_url") or "").strip()
    file_id = str(payload.get("file_id") or "").strip()
    file_name = str(payload.get("file_name") or "").strip()

    if not file_url and not file_id:
        return JsonResponse({"error": "file_url or file_id is required"}, status=400)

    field_id = str(payload.get("field_id") or "").strip()
    if not field_id and not is_task_bulk_attach:
        return JsonResponse({"error": "field_id is required"}, status=400)

    filter_params = payload.get("filter") or {}
    if not isinstance(filter_params, dict):
        filter_params = {}

    portal_member_id = getattr(account, "member_id", "")
    portal_domain = getattr(account, "domain_url", "")

    entity_labels = {"lead": "Лиды", "contact": "Контакты", "company": "Компании", "deal": "Сделки", "task": "Задачи"}
    display_name = file_name or (file_id and "загруженный файл") or "файл из URL"
    original_filename = f"Массовое добавление — {entity_labels.get(entity_type, entity_type)}: {display_name}"

    session = ImportSession.objects.create(
        portal_member_id=portal_member_id,
        portal_domain=portal_domain,
        created_by_b24_user_id=getattr(account, "b24_user_id", 0),
        entity_type=ImportSession.EntityType.TASK_ATTACHMENT if is_task_bulk_attach else CRM_FILES_ENTITY_TYPES[entity_type],
        source_format="bulk_attach",
        status=ImportSession.Status.DRAFT,
        original_filename=original_filename,
        summary={
            "bulk_attach": {
                "mode": "task" if is_task_bulk_attach else "crm",
                "entity_type": entity_type,
                "filter": filter_params,
                "file_url": file_url,
                "file_id": file_id,
                "file_name": file_name,
                **({"field_id": field_id} if field_id else {}),
            }
        },
    )

    return JsonResponse({"item": serialize_session(session)}, status=201)


@xframe_options_exempt
@csrf_exempt
@require_http_methods(["POST"])
@log_errors("bulk_attach_session_run")
@auth_required
def bulk_attach_session_run(request: AuthorizedRequest, session_id):
    account = request.bitrix24_account
    portal_member_id = getattr(account, "member_id", "")
    portal_domain = getattr(account, "domain_url", "")

    session = load_portal_session(portal_member_id, portal_domain, session_id)
    if session is None:
        return JsonResponse({"error": "Session not found"}, status=404)

    if not has_permission(account, "sessions.run"):
        return permission_denied_response()

    if session.status not in (ImportSession.Status.DRAFT, ImportSession.Status.FAILED):
        return JsonResponse({"error": f"Session cannot be run in status: {session.status}"}, status=400)

    if (session.summary or {}).get("bulk_attach") is None:
        return JsonResponse({"error": "Session is not a bulk attach session"}, status=400)

    session.status = ImportSession.Status.RUNNING
    session.last_error = ""
    session.save(update_fields=["status", "last_error", "updated_at"])

    if is_import_queue_enabled():
        from .services.background_jobs import enqueue_bulk_attach_session_run
        enqueue_bulk_attach_session_run(session, account)
        return JsonResponse({"item": serialize_session(session)})

    bulk_config = (session.summary or {}).get("bulk_attach") or {}
    is_task_bulk_attach = str(bulk_config.get("mode") or "").strip() == "task"
    if is_task_bulk_attach:
        from .services.task_bulk_attach import execute_task_bulk_attach
    else:
        from .services.bulk_attach import execute_bulk_attach
    try:
        result = execute_task_bulk_attach(session=session, account=account) if is_task_bulk_attach else execute_bulk_attach(session=session, account=account)
    except Exception as error:
        session.refresh_from_db()
        session.status = ImportSession.Status.FAILED
        session.last_error = safe_format_import_error(error)
        session.save(update_fields=["status", "last_error", "updated_at"])
        return JsonResponse({"error": safe_format_import_error(error)}, status=500)

    session.refresh_from_db()
    if session.status != ImportSession.Status.CANCELLED:
        session.status = ImportSession.Status.COMPLETED
        session.save(update_fields=["status", "updated_at"])

    return JsonResponse({"item": serialize_session(session), "result": result})
