import csv
import os
import re
from datetime import timedelta
from io import StringIO, TextIOWrapper
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

import xlrd

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from main.utils import AuthorizedRequest
from main.utils.decorators import auth_required, log_errors

from .models import ImportSession, ImportTemplate, ImporterUserRole
from .services.b24_fields import (
    SMART_PROCESS_ENTITY_TYPE,
    build_linked_entities_payload,
    fetch_entity_fields,
    fetch_smart_process_types,
    normalize_smart_process_entity_config,
)
from .services.background_jobs import (
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
from .services.error_messages import format_import_error
from .services.import_execution import execute_dry_run, execute_import, normalize_entity_dedup_settings
from .services.mapping import build_candidate_mapping, normalize_saved_mapping, resolve_field_item_value
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
from .services.user_resolution import BitrixUserResolver, list_bitrix_users
from .services.validation import build_validation_result


XLSX_MAIN_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
XLSX_REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
CELL_REF_RE = re.compile(r"([A-Z]+)")

MAX_IMPORT_ROWS = 100_000

_ALLOWED_UPLOAD_EXTENSIONS = {".xlsx", ".xls", ".csv"}
_XLSX_MAGIC = b"PK\x03\x04"          # ZIP / OOXML
_XLS_MAGIC  = b"\xd0\xcf\x11\xe0"    # OLE2 Compound Document
_MAX_UPLOAD_FILENAME_LENGTH = 200


def get_max_import_file_size_bytes() -> int:
    return int(getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", 50 * 1024 * 1024) or 50 * 1024 * 1024)


def get_max_import_file_size_megabytes() -> int:
    return max(1, get_max_import_file_size_bytes() // (1024 * 1024))


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


def normalize_task_defaults(payload, account=None) -> dict:
    if not isinstance(payload, dict):
        return {}

    raw_default_responsible_id = payload.get("default_responsible_id")
    raw_default_comment_author_id = payload.get("default_comment_author_id")
    if raw_default_responsible_id is None and isinstance(payload.get("task_defaults"), dict):
        raw_default_responsible_id = payload.get("task_defaults", {}).get("default_responsible_id")
    if raw_default_comment_author_id is None and isinstance(payload.get("task_defaults"), dict):
        raw_default_comment_author_id = payload.get("task_defaults", {}).get("default_comment_author_id")

    normalized_default_responsible_id = str(raw_default_responsible_id or "").strip()
    normalized_default_comment_author_id = str(raw_default_comment_author_id or "").strip()
    if not normalized_default_responsible_id and not normalized_default_comment_author_id:
        return {}

    if account is not None and normalized_default_responsible_id:
        resolved_default_responsible_id = BitrixUserResolver(account).resolve(normalized_default_responsible_id)
        if resolved_default_responsible_id is None:
            raise ValueError("Default responsible user must be a valid Bitrix user")
        normalized_default_responsible_id = str(resolved_default_responsible_id)

    if account is not None and normalized_default_comment_author_id:
        resolved_default_comment_author_id = BitrixUserResolver(account).resolve(normalized_default_comment_author_id)
        if resolved_default_comment_author_id is None:
            raise ValueError("Default comment author must be a valid Bitrix user")
        normalized_default_comment_author_id = str(resolved_default_comment_author_id)

    task_defaults = {}
    if normalized_default_responsible_id:
        task_defaults["default_responsible_id"] = normalized_default_responsible_id
    if normalized_default_comment_author_id:
        task_defaults["default_comment_author_id"] = normalized_default_comment_author_id
    return task_defaults


def build_task_default_field_values(entity_type: str, task_defaults: dict | None) -> dict:
    if not isinstance(task_defaults, dict):
        return {}

    if entity_type == ImportSession.EntityType.TASK:
        default_responsible_id = str(task_defaults.get("default_responsible_id") or "").strip()
        if not default_responsible_id:
            return {}

        return {
            "RESPONSIBLE_ID": default_responsible_id,
        }

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
            created_ids.append(record_id)
        elif status == "updated":
            updated_rows += 1
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

    return build_import_result_summary(merged_results)


def normalize_per_row_decisions(raw: object) -> dict:
    if not isinstance(raw, dict):
        return {}
    result = {}
    for row_num, decision in raw.items():
        d = str(decision or "").strip().lower()
        if d in ("create", "update", "skip"):
            result[str(row_num)] = d
    return result


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
                    "path": f"xl/{target}",
                }
            )

    if not sheets:
        raise ValueError("Workbook does not contain sheets")

    return sheets, worksheet_files, shared_strings_xml


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

    sheets, _worksheet_files, _shared_strings_xml = read_xlsx_archive(session)
    sheet_names = [sheet["name"] for sheet in sheets]
    if not sheet_names:
        raise ValueError("Workbook does not contain sheets")

    return sheet_names


def extract_rows_from_xlsx_sheet(sheet_xml: bytes, shared_strings: list[str] | None = None, preview_limit: int | None = 20):
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

            inline_string = cell.find("main:is/main:t", XLSX_MAIN_NS)
            if inline_string is not None and inline_string.text is not None:
                value = inline_string.text
            else:
                value_node = cell.find("main:v", XLSX_MAIN_NS)
                value = value_node.text if value_node is not None and value_node.text is not None else ""
                if cell.attrib.get("t") == "s":
                    try:
                        value = (shared_strings or [])[int(value)]
                    except (IndexError, TypeError, ValueError):
                        value = ""

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

    columns = [column_index_to_letter(index) for index in range(1, max_columns + 1)]
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
        return extract_rows_from_xls(session, selected_sheet_name, preview_limit=preview_limit)

    if session.source_format != ImportSession.SourceFormat.XLSX:
        raise ValueError("Unsupported source format")

    sheets, worksheet_files, shared_strings_xml = read_xlsx_archive(session)
    selected_sheet = next((sheet for sheet in sheets if sheet["name"] == selected_sheet_name), None)
    if selected_sheet is None:
        raise ValueError("Selected sheet does not exist")

    sheet_xml = worksheet_files.get(selected_sheet["path"])
    if sheet_xml is None:
        raise ValueError("Unable to read workbook preview")

    shared_strings = parse_shared_strings(shared_strings_xml)
    return extract_rows_from_xlsx_sheet(sheet_xml, shared_strings=shared_strings, preview_limit=preview_limit)


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
@require_http_methods(["GET", "POST"])
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

        return JsonResponse({"items": [serialize_session(item) for item in sessions]})

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

    session = ImportSession.objects.create(
        portal_member_id=portal_member_id,
        portal_domain=portal_domain,
        created_by_b24_user_id=getattr(account, "b24_user_id", 0),
        entity_type=entity_type,
        source_format=source_format,
        status=ImportSession.Status.DRAFT,
        original_filename=original_filename,
        import_settings={"entity_config": entity_config} if entity_config else {},
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
        candidate_mapping = build_candidate_mapping(structure["headers"], columns, fields)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

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
        **(session.import_settings if isinstance(session.import_settings, dict) else {}),
        "mapping": saved_mapping,
        "dedup": saved_dedup,
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
                "candidate_mapping": candidate_mapping,
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

    candidate_mapping = build_candidate_mapping(headers, columns, fields)
    import_settings = session.import_settings if isinstance(session.import_settings, dict) else {}
    saved_mapping = import_settings.get("mapping", {})
    if not isinstance(saved_mapping, dict):
        saved_mapping = {}
    task_defaults = normalize_task_defaults(import_settings.get("task_defaults", {}))
    try:
        saved_dedup = normalize_entity_dedup_settings(session.entity_type, import_settings.get("dedup", {}))
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
                    "default_comment_author_id": (request.data or {}).get("default_comment_author_id"),
                    "task_defaults": import_settings.get("task_defaults", {}),
                },
                account=account,
            )
        except ValueError as error:
            return JsonResponse({"error": str(error)}, status=400)

        session.import_settings = {
            **import_settings,
            "mapping": saved_mapping,
            "dedup": saved_dedup,
            "task_defaults": task_defaults,
        }
        session.last_error = ""
        session.save(update_fields=["import_settings", "last_error", "updated_at"])

    observed_values = {}
    selected_sheet_name = preview_data.get("selected_sheet_name") or session.source_sheet_name
    mapping_for_observed_values = saved_mapping if saved_mapping else candidate_mapping
    try:
        task_user_options = list_bitrix_users(account) if session.entity_type in {
            ImportSession.EntityType.TASK,
            ImportSession.EntityType.TASK_COMMENT,
        } else []
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    if selected_sheet_name and mapping_has_observed_value_fields(fields, mapping_for_observed_values):
        try:
            _columns, rows, row_numbers = extract_preview_rows(session, str(selected_sheet_name), preview_limit=None)
        except ValueError as error:
            return JsonResponse({"error": str(error)}, status=400)

        observed_values = build_observed_mapping_values(
            rows=rows,
            row_numbers=row_numbers,
            data_start_row=max(1, int(session.data_start_row or preview_data.get("data_start_row") or 1)),
            fields=fields,
            mapping=mapping_for_observed_values,
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
                "candidate_mapping": candidate_mapping,
                "saved_mapping": saved_mapping,
                "saved_dedup": saved_dedup,
                "task_defaults": task_defaults,
                "task_user_options": task_user_options,
                **({"linked_entities": linked_entities} if linked_entities else {}),
                "observed_values": observed_values,
                "unmapped_values": unmapped_values,
                "unmapped_value_count": count_mapping_values(unmapped_values),
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
        fields = fetch_session_entity_fields(account, session)
        _columns, rows, row_numbers = extract_preview_rows(session, str(selected_sheet_name), preview_limit=None)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    observed_values = build_observed_mapping_values(
        rows=rows,
        row_numbers=row_numbers,
        data_start_row=max(1, int(session.data_start_row or preview_data.get("data_start_row") or 1)),
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
                **validation_result,
            }
        }
    )


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

    preview_data = session.preview_data if isinstance(session.preview_data, dict) else {}
    columns = preview_data.get("columns")
    selected_sheet_name = preview_data.get("selected_sheet_name") or session.source_sheet_name
    if not isinstance(columns, list) or not columns or not selected_sheet_name:
        return JsonResponse({"error": "Preview data is required before dry run"}, status=400)

    import_settings = session.import_settings if isinstance(session.import_settings, dict) else {}
    saved_mapping = import_settings.get("mapping", {})
    if not isinstance(saved_mapping, dict) or not saved_mapping:
        return JsonResponse({"error": "Saved mapping is required before dry run"}, status=400)
    task_default_field_values = build_task_default_field_values(
        session.entity_type,
        normalize_task_defaults(import_settings.get("task_defaults", {})),
    )
    try:
        saved_dedup = normalize_entity_dedup_settings(session.entity_type, import_settings.get("dedup", {}))
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    summary = session.summary if isinstance(session.summary, dict) else {}
    validation_summary = summary.get("validation")
    if not isinstance(validation_summary, dict):
        return JsonResponse({"error": "Validation is required before dry run"}, status=400)

    try:
        fields = fetch_session_entity_fields(account, session)
        _columns, rows, row_numbers = extract_preview_rows(session, str(selected_sheet_name), preview_limit=None)
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
            default_field_values=task_default_field_values,
        )
    except Exception as error:
        return JsonResponse({"error": str(error)}, status=400)

    session.summary = {
        **summary,
        "dry_run": dry_run_result,
    }
    session.last_error = ""
    session.save(update_fields=["summary", "last_error", "updated_at"])

    return JsonResponse(
        {
            "item": {
                "session_id": str(session.id),
                "status": session.status,
                **dry_run_result,
            }
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
    if not isinstance(validation_summary, dict):
        raise ValueError("Validation is required before import execution")

    session.status = ImportSession.Status.RUNNING
    session.last_error = ""
    session.processed_rows = 0
    session.successful_rows = 0
    session.failed_rows = 0
    session.save(update_fields=["status", "last_error", "processed_rows", "successful_rows", "failed_rows", "updated_at"])

    def _save_progress(*, checked_rows, created_rows, updated_rows, failed_rows):
        session.processed_rows = checked_rows
        session.successful_rows = created_rows + updated_rows
        session.failed_rows = failed_rows
        session.save(update_fields=["processed_rows", "successful_rows", "failed_rows", "updated_at"])

    try:
        fields = fetch_session_entity_fields(account, session)
        _columns, rows, row_numbers = extract_preview_rows(session, str(selected_sheet_name), preview_limit=None)
        session.total_rows = sum(1 for rn in row_numbers if rn >= session.data_start_row)
        if session.total_rows > MAX_IMPORT_ROWS:
            raise ValueError(
                f"Файл содержит слишком много строк данных ({session.total_rows:,}). "
                f"Максимум: {MAX_IMPORT_ROWS:,} строк за один импорт."
            )
        session.save(update_fields=["total_rows", "updated_at"])
        import_result = execute_import(
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
            per_row_decisions=normalized_per_row_decisions,
            progress_callback=_save_progress,
            entity_config=get_session_entity_config(session),
        )
    except Exception as error:
        session.status = ImportSession.Status.FAILED
        session.last_error = format_import_error(error)
        session.save(update_fields=["status", "last_error", "updated_at"])
        raise

    session.summary = {
        **summary,
        "import_run": import_result,
    }
    session.status = ImportSession.Status.CANCELLED if import_result.get("cancelled") else ImportSession.Status.COMPLETED
    session.processed_rows = import_result["checked_rows"]
    session.successful_rows = import_result["created_rows"] + import_result.get("updated_rows", 0)
    session.failed_rows = import_result["failed_rows"]
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

    if per_row_decisions:
        import_settings = {**import_settings, "per_row_decisions": per_row_decisions}
        session.import_settings = import_settings
        session.save(update_fields=["import_settings", "updated_at"])

    summary = session.summary if isinstance(session.summary, dict) else {}
    validation_summary = summary.get("validation")
    if not isinstance(validation_summary, dict):
        return JsonResponse({"error": "Validation is required before import execution"}, status=400)

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
        enqueue_import_session_run(session, account)
        session.refresh_from_db()
        return JsonResponse({"item": serialize_session_response_item(session)}, status=202)

    try:
        import_item = execute_import_session_run_now(
            session=session,
            account=account,
            per_row_decisions=per_row_decisions,
        )
    except Exception as error:
        return JsonResponse({"error": format_import_error(error)}, status=400)

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

    session.status = ImportSession.Status.CANCELLED
    session.last_error = ""
    session.save(update_fields=["status", "last_error", "updated_at"])
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
        )
    except Exception as error:
        session.status = ImportSession.Status.FAILED
        session.last_error = format_import_error(error)
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
        session.save(
            update_fields=["status", "last_error", "processed_rows", "successful_rows", "failed_rows", "updated_at"]
        )
        enqueue_import_session_retry(session, account)
        session.refresh_from_db()
        return JsonResponse({"item": serialize_session_response_item(session)}, status=202)

    try:
        retry_item = execute_import_session_retry_now(session=session, account=account)
    except Exception as error:
        return JsonResponse({"error": format_import_error(error)}, status=400)

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
        **({} if not preview_meta else {"csv_delimiter": preview_meta.get("csv_delimiter")}),
    }
    session.last_error = ""
    session.save(
        update_fields=[
            "source_sheet_name",
            "header_row",
            "data_start_row",
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
@log_errors("crm_filter_preview")
@auth_required
def crm_filter_preview(request: AuthorizedRequest):
    from .services.bulk_attach import fetch_crm_entities_page, SUPPORTED_ENTITY_TYPES, _extract_entity_title

    account = request.bitrix24_account
    if not has_permission(account, "sessions.create"):
        return permission_denied_response()

    import json
    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    entity_type = str(payload.get("entity_type") or "").strip()
    if entity_type not in SUPPORTED_ENTITY_TYPES:
        return JsonResponse({"error": f"Unsupported entity type: {entity_type}"}, status=400)

    filter_params = payload.get("filter") or {}
    if not isinstance(filter_params, dict):
        filter_params = {}

    try:
        page = fetch_crm_entities_page(account, entity_type, filter_params, start=0)
    except Exception as error:
        return JsonResponse({"error": str(error)}, status=500)

    sample = []
    for item in page["items"][:10]:
        if isinstance(item, dict):
            raw_id = item.get("ID") or item.get("id")
            sample.append({
                "id": int(raw_id) if raw_id is not None else None,
                "title": _extract_entity_title(entity_type, item),
            })

    return JsonResponse({
        "total": page["total"],
        "has_more": page["next"] is not None,
        "sample": sample,
    })


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
    if entity_type not in SUPPORTED_ENTITY_TYPES:
        return JsonResponse({"error": f"Unsupported entity type: {entity_type}"}, status=400)

    file_url = str(payload.get("file_url") or "").strip()
    if not file_url:
        return JsonResponse({"error": "file_url is required"}, status=400)

    field_id = str(payload.get("field_id") or "").strip()
    if not field_id:
        return JsonResponse({"error": "field_id is required"}, status=400)

    filter_params = payload.get("filter") or {}
    if not isinstance(filter_params, dict):
        filter_params = {}

    file_name = str(payload.get("file_name") or "").strip()

    portal_member_id = int(getattr(account, "portal_member_id", 0) or 0)
    portal_domain = str(getattr(account, "portal_domain", "") or "")

    session = ImportSession.objects.create(
        portal_member_id=portal_member_id,
        portal_domain=portal_domain,
        entity_type=CRM_FILES_ENTITY_TYPES[entity_type],
        source_format="bulk_attach",
        status=ImportSession.Status.DRAFT,
        summary={
            "bulk_attach": {
                "entity_type": entity_type,
                "filter": filter_params,
                "file_url": file_url,
                "field_id": field_id,
                "file_name": file_name,
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

    from .services.bulk_attach import execute_bulk_attach

    session.status = ImportSession.Status.RUNNING
    session.last_error = ""
    session.save(update_fields=["status", "last_error", "updated_at"])

    try:
        result = execute_bulk_attach(session=session, account=account)
    except Exception as error:
        session.refresh_from_db()
        session.status = ImportSession.Status.FAILED
        session.last_error = format_import_error(error)
        session.save(update_fields=["status", "last_error", "updated_at"])
        return JsonResponse({"error": format_import_error(error)}, status=500)

    session.refresh_from_db()
    if session.status != ImportSession.Status.CANCELLED:
        session.status = ImportSession.Status.COMPLETED
        session.save(update_fields=["status", "updated_at"])

    return JsonResponse({"item": serialize_session(session), "result": result})
