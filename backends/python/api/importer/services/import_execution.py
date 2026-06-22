import os
import re
import time
import logging

from b24pysdk.error import BitrixOAuthInvalidGrant, BitrixRequestTimeout
from b24pysdk.bitrix_api.requests import BitrixAPIBatchRequest, BitrixAPIRequest

from .validation import (
    normalize_value,
    parse_boolean_value,
    parse_date_value,
    parse_datetime_value,
    parse_integer_value,
    parse_number_value,
    normalize_currency_id_value,
    resolve_default_field_value,
    resolve_field_validation_type,
    row_has_values,
    split_field_values,
)
from .task_attachments import attach_file_to_crm_entity, attach_file_to_task, attach_uf_file_field, download_attachment_source
from .error_messages import (
    get_import_error_text,
    is_daily_invitation_limit_error,
    iter_error_messages,
    safe_format_import_error,
)
from .report_metadata import build_import_result_report_meta
from .task_resolution import BitrixTaskResolver, is_task_reference_field
from .user_resolution import BitrixUserResolver, is_task_user_reference_field
from .value_normalization import build_discrete_value_keys, resolve_value_mapping
from .b24_fields import SMART_PROCESS_ENTITY_TYPE, get_linked_import_schema, normalize_smart_process_entity_config


TASK_CHILD_API_METHODS = {
    "task_comment": "tasks.task.chat.message.send",
    "task_checklist_item": "tasks.task.checklist.add",
}

TASK_ENTITY_TYPES = {"task", "task_comment", "task_checklist_item", "task_attachment"}
CRM_FILES_ENTITY_TYPES = {"crm_files_lead", "crm_files_contact", "crm_files_company", "crm_files_deal"}
_UF_FILE_ENTITY_TYPES = frozenset({"lead", "contact", "company", "deal", SMART_PROCESS_ENTITY_TYPE,
    "linked_company_contact", "linked_company_deal",
    "linked_contact_company", "linked_contact_deal",
    "linked_deal_company", "linked_deal_contact"})
_UF_FILE_FIELD_TYPES = frozenset({"file", "disk_file"})
CRM_ACTIVITY_ENTITY_TYPES = {"crm_activity", "crm_note"}
CRM_ACTIVITY_COMMUNICATION_TYPES = {
    "2": "PHONE",
    "4": "EMAIL",
}
HR_ENTITY_TYPES = {"user", "department"}
LINKED_COMPANY_CONTACT_ENTITY_TYPE = "linked_company_contact"
LINKED_COMPANY_DEAL_ENTITY_TYPE = "linked_company_deal"
LINKED_CONTACT_COMPANY_ENTITY_TYPE = "linked_contact_company"
LINKED_CONTACT_DEAL_ENTITY_TYPE = "linked_contact_deal"
LINKED_DEAL_COMPANY_ENTITY_TYPE = "linked_deal_company"
LINKED_DEAL_CONTACT_ENTITY_TYPE = "linked_deal_contact"
LINKED_RELATION_STRATEGIES = {
    LINKED_COMPANY_CONTACT_ENTITY_TYPE: {
        "mode": "field",
        "field": "COMPANY_ID",
    },
    LINKED_COMPANY_DEAL_ENTITY_TYPE: {
        "mode": "field",
        "field": "COMPANY_ID",
    },
    LINKED_CONTACT_COMPANY_ENTITY_TYPE: {
        "mode": "contact_company_binding",
    },
    LINKED_CONTACT_DEAL_ENTITY_TYPE: {
        "mode": "field",
        "field": "CONTACT_ID",
    },
    LINKED_DEAL_COMPANY_ENTITY_TYPE: {
        "mode": "parent_field",
        "field": "COMPANY_ID",
    },
    LINKED_DEAL_CONTACT_ENTITY_TYPE: {
        "mode": "deal_contact_binding",
    },
}

SUPPORTED_DEDUP_STRATEGIES = {"create", "skip", "update", "ask"}
SUPPORTED_DEDUP_FIELDS = {"EMAIL", "PHONE", "TITLE"}   # legacy whitelist kept for reference
_DEDUP_FIELD_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')    # any valid Bitrix24 field name
BITRIX_MULTIFIELD_IDS = {"PHONE", "EMAIL", "WEB", "IM"}
TASK_CHILD_ENTITY_TYPES = {"task_comment", "task_checklist_item"}


def _read_non_negative_float_env(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.getenv(name, default)))
    except (TypeError, ValueError):
        return max(0.0, float(default))


def _read_positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, default)))
    except (TypeError, ValueError):
        return max(1, int(default))


BITRIX_ROW_DELAY = _read_non_negative_float_env("BITRIX_ROW_DELAY", 0.1)
BITRIX_BATCH_DELAY = _read_non_negative_float_env("BITRIX_BATCH_DELAY", 1.0)
BATCH_SIZE = _read_positive_int_env("BATCH_SIZE", 50)
_ENTITY_BATCH_SIZES = {
    "lead": _read_positive_int_env("LEAD_BATCH_SIZE", 40),
    "deal": _read_positive_int_env("DEAL_BATCH_SIZE", 40),
    "contact": _read_positive_int_env("CONTACT_BATCH_SIZE", 40),
    "company": _read_positive_int_env("COMPANY_BATCH_SIZE", 40),
}
_BATCH_SIZE_MIN = _read_positive_int_env("BATCH_SIZE_MIN", 5)
PROGRESS_SAVE_INTERVAL = _read_positive_int_env("IMPORT_PROGRESS_SAVE_INTERVAL", 100)
_RATE_LIMIT_KEYWORDS = frozenset(["query_limit_exceeded", "too many requests", "rate limit", "overloaded", "429"])
_RATE_LIMIT_RETRY_WAITS = [5, 15, 30]
_OPERATION_TIME_LIMIT_KEYWORDS = frozenset([
    "operation time limit",
    "operation_time_limit",
    "method is blocked due to operation time limit",
    "unknown error",  # Bitrix24 returns this for user.add when operation time limit is exceeded
])
_OPERATION_TIME_LIMIT_RETRY_WAITS = [30, 60, 120, 300]

_CRM_BATCH_CREATE_METHODS = {
    "lead": "crm.lead.add",
    "contact": "crm.contact.add",
    "company": "crm.company.add",
    "deal": "crm.deal.add",
}

_CRM_BATCH_LIST_METHODS = {
    "lead": "crm.lead.list",
    "contact": "crm.contact.list",
    "company": "crm.company.list",
    "deal": "crm.deal.list",
}


def _get_batch_size(entity_type: str) -> int:
    return _ENTITY_BATCH_SIZES.get(entity_type, BATCH_SIZE)


def _is_batch_eligible(entity_type: str, dedup_settings: dict) -> bool:
    return entity_type in _CRM_BATCH_CREATE_METHODS and dedup_settings.get("strategy") == "create"


def _extract_uf_file_fields(row_payload: dict, fields_meta: list) -> tuple[dict, dict]:
    """Split payload into (uf_file_fields, remaining_payload).

    Returns ({field_id: (url_str, field_type)}, rest_of_payload).
    Only fields whose metadata type is in _UF_FILE_FIELD_TYPES and whose value is non-empty are extracted.
    """
    field_meta_by_id = {str(f.get("id", "")): f for f in (fields_meta or []) if f.get("id")}
    file_fields: dict = {}
    rest_payload: dict = {}
    for field_id, value in row_payload.items():
        meta = field_meta_by_id.get(str(field_id), {})
        field_type = str(meta.get("type", "") or "").lower()
        url_str = str(value or "").strip()
        if field_type in _UF_FILE_FIELD_TYPES and url_str:
            file_fields[str(field_id)] = (url_str, field_type)
        else:
            rest_payload[field_id] = value
    return file_fields, rest_payload


def _attach_uf_file_fields(
    account,
    entity_type: str,
    record_id: int,
    file_fields: dict,
    *,
    context: dict | None = None,
) -> list[str]:
    """Attach UF_ file fields to an existing CRM record. Returns a list of per-field error messages."""
    entity_type_id = None
    if entity_type == SMART_PROCESS_ENTITY_TYPE and isinstance(context, dict):
        entity_config = context.get("entity_config") or {}
        if isinstance(entity_config, dict):
            entity_type_id = entity_config.get("entityTypeId")

    resolved_entity_type = get_linked_parent_entity_type(entity_type) if is_linked_import_entity_type(entity_type) else entity_type
    errors: list[str] = []
    for field_id, (file_url, field_type) in file_fields.items():
        try:
            attach_uf_file_field(
                account,
                entity_type=resolved_entity_type,
                record_id=record_id,
                field_id=field_id,
                field_type=field_type,
                file_url=file_url,
                entity_type_id=entity_type_id,
            )
        except Exception as exc:
            errors.append(f"{field_id}: {safe_format_import_error(exc)}")
    return errors


def _flush_crm_batch(account, entity_type: str, pending_batch: list) -> tuple:
    method = _CRM_BATCH_CREATE_METHODS[entity_type]
    batch_requests = {
        str(i): BitrixAPIRequest(
            bitrix_token=account,
            api_method=method,
            params={"fields": payload},
        )
        for i, (_row_number, payload) in enumerate(pending_batch)
    }
    batch_response = BitrixAPIBatchRequest(
        bitrix_token=account,
        bitrix_api_requests=batch_requests,
        halt=False,
    )
    batch_result = batch_response.result
    raw_results = _normalize_batch_collection(batch_result.result)
    raw_errors = _normalize_batch_collection(batch_result.result_error)

    flush_results = []
    created_count = 0
    failed_count = 0
    created_ids = []

    for i, (row_number, row_payload) in enumerate(pending_batch):
        key = str(i)
        if key in raw_errors:
            failed_count += 1
            flush_results.append(
                {
                    "row_number": row_number,
                    "status": "failed",
                    "error": safe_format_import_error(raw_errors[key]),
                    **build_import_result_report_meta(entity_type, row_payload=row_payload),
                }
            )
        else:
            record_id = _extract_record_id_from_batch_result(raw_results.get(key))
            if record_id is None:
                failed_count += 1
                flush_results.append(
                    {
                        "row_number": row_number,
                        "status": "failed",
                        "error": get_import_error_text("missing_record_id"),
                        **build_import_result_report_meta(entity_type, row_payload=row_payload),
                    }
                )
                continue
            created_count += 1
            result_item = {
                "row_number": row_number,
                "status": "created",
                **build_import_result_report_meta(entity_type, row_payload=row_payload, record_id=record_id),
            }
            if record_id is not None:
                created_ids.append(record_id)
                result_item["record_id"] = record_id
            flush_results.append(result_item)

    return flush_results, created_count, failed_count, created_ids


def _is_rate_limit_error(error) -> bool:
    normalized_messages = [message.lower() for message in iter_error_messages(error)]
    return any(keyword in message for message in normalized_messages for keyword in _RATE_LIMIT_KEYWORDS)


def _is_operation_time_limit_error(error, *, allow_unknown_error: bool = True) -> bool:
    normalized_messages = [message.lower() for message in iter_error_messages(error)]
    for message in normalized_messages:
        for keyword in _OPERATION_TIME_LIMIT_KEYWORDS:
            if keyword == "unknown error" and not allow_unknown_error:
                continue
            if keyword in message:
                return True
    return False


def _is_timeout_error(error) -> bool:
    if isinstance(error, BitrixRequestTimeout):
        return True

    normalized_error = str(error).lower()
    return "timed out" in normalized_error or "timeout" in normalized_error


def _bitrix_retry(fn, on_pause=None, on_resume=None, allow_unknown_error_as_operation_time_limit=True):
    attempt = 0

    while True:
        try:
            return fn()
        except Exception as error:
            if is_daily_invitation_limit_error(error):
                raise
            if _is_operation_time_limit_error(error, allow_unknown_error=allow_unknown_error_as_operation_time_limit):
                retry_waits = _OPERATION_TIME_LIMIT_RETRY_WAITS
            elif _is_rate_limit_error(error):
                retry_waits = _RATE_LIMIT_RETRY_WAITS
            else:
                raise

            if attempt >= len(retry_waits):
                raise

            wait_seconds = retry_waits[attempt]
            if callable(on_pause):
                try:
                    on_pause(wait_seconds)
                except Exception:
                    pass
            time.sleep(wait_seconds)
            if callable(on_resume):
                try:
                    on_resume()
                except Exception:
                    pass
            attempt += 1


def _resolve_fatal_import_error(error, *, entity_type: str) -> str:
    if entity_type != "user":
        return ""

    normalized_messages = [message.lower() for message in iter_error_messages(error)]
    if is_daily_invitation_limit_error(error):
        fatal_error = safe_format_import_error(error)
    elif any("unknown error" in message for message in normalized_messages):
        fatal_error = get_import_error_text("invitation_unknown")
    else:
        return ""

    logging.warning(
        "Stopping user import because Bitrix24 returned a permanent invitation error: %s | messages=%s | json_response=%s",
        fatal_error,
        list(iter_error_messages(error)),
        getattr(error, "json_response", None),
    )
    return fatal_error


def _flush_crm_batch_with_fallback(account, entity_type: str, pending_batch: list, *, on_pause=None, on_resume=None) -> tuple:
    try:
        return _bitrix_retry(
            lambda: _flush_crm_batch(account, entity_type, pending_batch),
            on_pause=on_pause,
            on_resume=on_resume,
        )
    except Exception as error:
        # Only split on pure network timeout: smaller sub-batches may succeed when
        # a large one times out at the HTTP layer.
        # Operation time limit is a server-side block — splitting does not help and
        # spawns O(N) retry trees that waste minutes without recovery.
        if len(pending_batch) <= 1 or not _is_timeout_error(error):
            raise

    middle_index = max(1, len(pending_batch) // 2)
    left_results, left_created, left_failed, left_ids = _flush_crm_batch_with_fallback(
        account,
        entity_type,
        pending_batch[:middle_index],
        on_pause=on_pause,
        on_resume=on_resume,
    )
    right_results, right_created, right_failed, right_ids = _flush_crm_batch_with_fallback(
        account,
        entity_type,
        pending_batch[middle_index:],
        on_pause=on_pause,
        on_resume=on_resume,
    )

    return (
        [*left_results, *right_results],
        left_created + right_created,
        left_failed + right_failed,
        [*left_ids, *right_ids],
    )


def _sleep_if_configured(delay: float) -> None:
    if delay > 0:
        time.sleep(delay)


def _report_progress(progress_callback, *, checked_rows: int, created_rows: int, updated_rows: int, failed_rows: int) -> None:
    if not callable(progress_callback):
        return
    if checked_rows <= 0 or checked_rows % PROGRESS_SAVE_INTERVAL != 0:
        return

    progress_callback(
        checked_rows=checked_rows,
        created_rows=created_rows,
        updated_rows=updated_rows,
        failed_rows=failed_rows,
    )


def _report_dry_run_progress(
    progress_callback,
    *,
    checked_rows: int,
    ready_rows: int,
    skipped_rows: int,
    pending_decision_rows: int,
) -> None:
    if not callable(progress_callback):
        return
    if checked_rows <= 0 or checked_rows % PROGRESS_SAVE_INTERVAL != 0:
        return

    progress_callback(
        checked_rows=checked_rows,
        ready_rows=ready_rows,
        skipped_rows=skipped_rows,
        pending_decision_rows=pending_decision_rows,
    )


def build_field_index(fields: list[dict]) -> dict[str, dict]:
    return {
        str(field.get("id")): field
        for field in fields
        if isinstance(field, dict) and field.get("id")
    }


def get_linked_entities(entity_type: str = LINKED_COMPANY_CONTACT_ENTITY_TYPE) -> list[dict]:
    schema = get_linked_import_schema(entity_type)
    if schema is None:
        return []

    return [dict(entity) for entity in schema["entities"]]


def get_linked_entity_ids(entity_type: str = LINKED_COMPANY_CONTACT_ENTITY_TYPE) -> list[str]:
    return [
        str(entity.get("id") or "").strip().lower()
        for entity in get_linked_entities(entity_type)
        if str(entity.get("id") or "").strip()
    ]


def get_linked_entity_prefix_map(entity_type: str = LINKED_COMPANY_CONTACT_ENTITY_TYPE) -> dict[str, str]:
    return {
        str(entity.get("id") or "").strip().lower(): str(entity.get("prefix") or "").strip()
        for entity in get_linked_entities(entity_type)
        if str(entity.get("id") or "").strip() and str(entity.get("prefix") or "").strip()
    }


def is_linked_import_entity_type(entity_type: str) -> bool:
    return get_linked_import_schema(str(entity_type or "").strip()) is not None


def get_linked_parent_entity_type(entity_type: str) -> str:
    linked_entity_ids = get_linked_entity_ids(entity_type)
    if len(linked_entity_ids) < 2:
        raise ValueError(f"Unsupported linked import entity type: {entity_type}")
    return linked_entity_ids[0]


def get_linked_child_entity_type(entity_type: str) -> str:
    linked_entity_ids = get_linked_entity_ids(entity_type)
    if len(linked_entity_ids) < 2:
        raise ValueError(f"Unsupported linked import entity type: {entity_type}")
    return linked_entity_ids[1]


def get_linked_child_link_field(entity_type: str) -> str:
    relation_strategy = LINKED_RELATION_STRATEGIES.get(str(entity_type or "").strip())
    child_link_field = str((relation_strategy or {}).get("field") or "").strip()
    if child_link_field:
        return child_link_field

    parent_entity_type = get_linked_parent_entity_type(entity_type)
    child_entity_type = get_linked_child_entity_type(entity_type)
    raise ValueError(f"Unsupported linked import entity relation: {parent_entity_type} -> {child_entity_type}")


def get_linked_relation_strategy(entity_type: str) -> dict:
    relation_strategy = LINKED_RELATION_STRATEGIES.get(str(entity_type or "").strip())
    if relation_strategy is None:
        raise ValueError(f"Unsupported linked import entity type: {entity_type}")
    return dict(relation_strategy)


def bind_deal_contact(account, *, deal_id, contact_id) -> None:
    response = BitrixAPIRequest(
        bitrix_token=account,
        api_method="crm.deal.contact.add",
        params={
            "id": deal_id,
            "fields": {
                "CONTACT_ID": contact_id,
            },
        },
    )
    unwrap_bitrix_result(response)


def bind_contact_company(account, *, contact_id, company_id) -> None:
    response = BitrixAPIRequest(
        bitrix_token=account,
        api_method="crm.contact.company.add",
        params={
            "id": contact_id,
            "fields": {
                "COMPANY_ID": company_id,
            },
        },
    )
    unwrap_bitrix_result(response)


def build_linked_field_groups(fields: list[dict], entity_type: str = LINKED_COMPANY_CONTACT_ENTITY_TYPE) -> dict[str, list[dict]]:
    linked_entity_ids = get_linked_entity_ids(entity_type)
    allowed_linked_entities = set(linked_entity_ids)
    grouped_fields = {entity_name: [] for entity_name in linked_entity_ids}

    for field in fields:
        if not isinstance(field, dict):
            continue

        linked_entity = str(field.get("linked_entity") or "").strip().lower()
        linked_source_id = str(field.get("linked_source_id") or "").strip()
        if linked_entity not in allowed_linked_entities or not linked_source_id:
            continue

        grouped_fields[linked_entity].append(
            {
                **field,
                "id": linked_source_id,
            }
        )

    return grouped_fields


def build_linked_mapping_groups(mapping: dict, fields: list[dict], entity_type: str = LINKED_COMPANY_CONTACT_ENTITY_TYPE) -> dict[str, dict]:
    field_by_id = build_field_index(fields)
    linked_entity_ids = get_linked_entity_ids(entity_type)
    allowed_linked_entities = set(linked_entity_ids)
    grouped_mapping = {entity_name: {} for entity_name in linked_entity_ids}

    for target_field, mapping_item in (mapping or {}).items():
        if not isinstance(mapping_item, dict):
            continue

        field = field_by_id.get(str(target_field))
        if field is None:
            continue

        linked_entity = str(field.get("linked_entity") or "").strip().lower()
        linked_source_id = str(field.get("linked_source_id") or "").strip()
        if linked_entity not in allowed_linked_entities or not linked_source_id:
            continue

        grouped_mapping[linked_entity][linked_source_id] = {
            **mapping_item,
            "target_field": linked_source_id,
        }

    return grouped_mapping


def format_bitrix_field_value(field: dict, value):
    field_id = str(field.get("id") or "").upper()
    field_type = str(field.get("type") or "").lower()
    is_multiple = bool(field.get("multiple"))

    if is_multiple and (field_type in {"phone", "email", "web", "im", "crm_multifield"} or field_id in BITRIX_MULTIFIELD_IDS):
        if isinstance(value, list):
            return [
                {
                    "VALUE": item,
                    "VALUE_TYPE": "WORK",
                }
                for item in value
                if normalize_value(item)
            ]
        return [
            {
                "VALUE": value,
                "VALUE_TYPE": "WORK",
            }
        ]

    if is_multiple:
        if isinstance(value, list):
            return value
        return [value]

    return value


def build_field_items_index(field: dict) -> dict[str, str]:
    items_index = {}

    for item in field.get("items", []):
        if not isinstance(item, dict):
            continue

        item_id = normalize_value(item.get("id"))
        item_title = normalize_value(item.get("title"))
        if item_id:
            for index_key in build_discrete_value_keys(item_id):
                items_index.setdefault(index_key, item_id)
        if item_title:
            for index_key in build_discrete_value_keys(item_title):
                items_index.setdefault(index_key, item_id)

    return items_index


def resolve_field_value(field: dict, value: str, mapping_item: dict) -> str:
    normalized_value = normalize_value(value)
    if not normalized_value:
        return ""

    value_mapping = mapping_item.get("value_mapping") if isinstance(mapping_item, dict) else None
    mapped_value = resolve_value_mapping(value_mapping, normalized_value)
    if mapped_value:
        return mapped_value

    if field.get("items"):
        items_index = build_field_items_index(field)
        for index_key in build_discrete_value_keys(normalized_value):
            resolved_value = items_index.get(index_key)
            if resolved_value:
                return resolved_value
        return normalized_value

    return normalized_value


def resolve_field_values(field: dict, value: str, mapping_item: dict) -> list[str]:
    resolved_values = []

    for item_value in split_field_values(field, value):
        resolved_value = resolve_field_value(field, item_value, mapping_item)
        if resolved_value:
            resolved_values.append(resolved_value)

    return resolved_values


def normalize_typed_field_value(field: dict, target_field: str, value, column_type_override: str = ""):
    normalized_value = normalize_value(value)
    if not normalized_value:
        return ""

    if str(target_field or "").upper() == "CURRENCY_ID":
        return normalize_currency_id_value(normalized_value)

    if is_task_reference_field(field, target_field):
        try:
            return parse_integer_value(normalized_value)
        except ValueError:
            return normalized_value

    field_type = resolve_field_validation_type(field, target_field, column_type_override)

    if field_type in {"file", "disk_file"}:
        return normalized_value

    if field_type in {"boolean", "bool"}:
        parsed_boolean_value = parse_boolean_value(normalized_value)
        field_id = str(field.get("id") or target_field or "").strip().upper()
        if field_id.startswith("UF_") and not field_id.startswith("UF_CRM_"):
            return "Y" if parsed_boolean_value else "N"
        return parsed_boolean_value

    if field_type in {"integer", "int"}:
        return parse_integer_value(normalized_value)

    if field_type in {"double", "float", "money", "number"}:
        return parse_number_value(normalized_value)

    if field_type == "date":
        return parse_date_value(normalized_value).strftime("%Y-%m-%d")

    if field_type == "datetime":
        return parse_datetime_value(normalized_value).strftime("%Y-%m-%dT%H:%M:%S")

    return normalized_value


def build_row_payload(
    row: list,
    columns: list[str],
    mapping: dict,
    fields: list[dict],
    account=None,
    user_resolver: BitrixUserResolver | None = None,
    default_field_values: dict | None = None,
) -> dict:
    column_index_by_name = {
        str(column): index
        for index, column in enumerate(columns)
    }
    field_by_id = build_field_index(fields)
    task_user_resolver = user_resolver or (BitrixUserResolver(account) if account is not None else None)
    task_resolver = BitrixTaskResolver(account) if account is not None else None

    payload = {}
    for target_field, mapping_item in mapping.items():
        if not isinstance(mapping_item, dict):
            continue

        column = str(mapping_item.get("column") or "")
        column_index = column_index_by_name.get(column)
        if column_index is None or column_index >= len(row):
            continue

        value = normalize_value(row[column_index])
        if not value:
            continue

        field = field_by_id.get(str(target_field), {})
        resolved_values = resolve_field_values(field, value, mapping_item)
        if not resolved_values:
            continue

        if is_task_user_reference_field(field, str(target_field)) and task_user_resolver is not None:
            resolved_user_ids = []
            for resolved_value in resolved_values:
                resolved_user_id = task_user_resolver.resolve(resolved_value)
                if resolved_user_id is None:
                    raise ValueError(f'Unable to resolve Bitrix user "{resolved_value}" for field "{target_field}"')
                resolved_user_ids.append(resolved_user_id)
            resolved_values = resolved_user_ids

        if is_task_reference_field(field, str(target_field)) and task_resolver is not None:
            resolved_task_ids = []
            for resolved_value in resolved_values:
                resolved_task_id = task_resolver.resolve(resolved_value)
                if resolved_task_id is None:
                    raise ValueError(f'Unable to resolve Bitrix task "{resolved_value}" for field "{target_field}"')
                resolved_task_ids.append(resolved_task_id)
            resolved_values = resolved_task_ids

        column_type_override = str(mapping_item.get("column_type") or "").strip().lower() if isinstance(mapping_item, dict) else ""
        normalized_values = [
            normalize_typed_field_value(field, str(target_field), resolved_value, column_type_override)
            for resolved_value in resolved_values
        ]
        normalized_values = [item for item in normalized_values if item != ""]
        if not normalized_values:
            continue

        payload_value = normalized_values if field.get("multiple") else normalized_values[0]
        payload[str(target_field)] = format_bitrix_field_value(field, payload_value)

    for field_id, field in field_by_id.items():
        default_value = resolve_default_field_value(default_field_values, field_id)
        if not default_value or field_id in payload:
            continue

        resolved_values = [default_value]
        if is_task_user_reference_field(field, str(field_id)) and task_user_resolver is not None:
            resolved_user_ids = []
            for resolved_value in resolved_values:
                resolved_user_id = task_user_resolver.resolve(resolved_value)
                if resolved_user_id is None:
                    raise ValueError(f'Unable to resolve Bitrix user "{resolved_value}" for field "{field_id}"')
                resolved_user_ids.append(resolved_user_id)
            resolved_values = resolved_user_ids

        normalized_values = [
            normalize_typed_field_value(field, str(field_id), resolved_value)
            for resolved_value in resolved_values
        ]
        normalized_values = [item for item in normalized_values if item != ""]
        if not normalized_values:
            continue

        payload_value = normalized_values if field.get("multiple") else normalized_values[0]
        payload[str(field_id)] = format_bitrix_field_value(field, payload_value)

    return payload


def build_linked_row_payload(
    row: list,
    columns: list[str],
    mapping: dict,
    fields: list[dict],
    entity_type: str = LINKED_COMPANY_CONTACT_ENTITY_TYPE,
    account=None,
    user_resolver: BitrixUserResolver | None = None,
    default_field_values: dict | None = None,
) -> dict:
    grouped_fields = build_linked_field_groups(fields, entity_type=entity_type)
    grouped_mapping = build_linked_mapping_groups(mapping, fields, entity_type=entity_type)
    linked_entity_ids = get_linked_entity_ids(entity_type)

    return {
        linked_entity: build_row_payload(
            row,
            columns,
            grouped_mapping.get(linked_entity, {}),
            grouped_fields.get(linked_entity, []),
            account=account,
            user_resolver=user_resolver,
            default_field_values=default_field_values,
        )
        for linked_entity in linked_entity_ids
    }


def get_invalid_row_numbers(validation_summary: dict) -> set[int]:
    invalid_rows = set()

    for issue in validation_summary.get("issues", []):
        if not isinstance(issue, dict):
            continue

        try:
            invalid_rows.add(int(issue.get("row_number")))
        except (TypeError, ValueError):
            continue

    return invalid_rows


def unwrap_bitrix_result(response):
    return getattr(response, "result", response)


def normalize_record_id(record_id):
    if record_id is None or isinstance(record_id, bool):
        return None
    try:
        return int(record_id)
    except (TypeError, ValueError):
        return record_id


def _normalize_batch_collection(collection) -> dict:
    if isinstance(collection, dict):
        return collection
    if isinstance(collection, list):
        normalized = {}
        for index, value in enumerate(collection):
            if value in (None, "", [], {}):
                continue
            normalized[str(index)] = value
        return normalized
    return {}


def _extract_record_id_from_batch_result(result):
    normalized_result = unwrap_bitrix_result(result)

    if isinstance(normalized_result, dict):
        nested_item = normalized_result.get("item")
        if isinstance(nested_item, dict):
            return normalize_record_id(nested_item.get("ID") or nested_item.get("id"))

        nested_result = normalized_result.get("result")
        if isinstance(nested_result, dict):
            nested_result_item = nested_result.get("item")
            if isinstance(nested_result_item, dict):
                return normalize_record_id(nested_result_item.get("ID") or nested_result_item.get("id"))
            return normalize_record_id(
                nested_result.get("ID") or nested_result.get("id") or nested_result.get("result")
            )

        return normalize_record_id(
            normalized_result.get("ID") or normalized_result.get("id") or normalized_result.get("result")
        )

    return normalize_record_id(normalized_result)


def build_crm_activity_communications(fields: dict) -> list[dict]:
    owner_type_id = normalize_value(fields.get("OWNER_TYPE_ID"))
    owner_id = normalize_value(fields.get("OWNER_ID"))
    type_id = normalize_value(fields.get("TYPE_ID"))
    communication_value = normalize_value(fields.get("COMMUNICATIONS_VALUE"))

    communication = {
        "ENTITY_ID": int(owner_id),
        "ENTITY_TYPE_ID": int(owner_type_id),
    }

    communication_type = CRM_ACTIVITY_COMMUNICATION_TYPES.get(type_id)
    if communication_type:
        if not communication_value:
            if communication_type == "PHONE":
                raise ValueError("COMMUNICATIONS_VALUE обязателен для звонка CRM")
            raise ValueError("COMMUNICATIONS_VALUE обязателен для email CRM")
        communication["TYPE"] = communication_type
        communication["VALUE"] = communication_value

    return [communication]


def normalize_dedup_settings(dedup_settings) -> dict:
    if not isinstance(dedup_settings, dict):
        return {
            "strategy": "create",
            "fields": [],
            "condition": "any",
        }

    strategy = str(dedup_settings.get("strategy") or "create").strip().lower()
    if strategy not in SUPPORTED_DEDUP_STRATEGIES:
        raise ValueError("Unsupported dedup strategy")

    normalized_fields = []
    for field_name in dedup_settings.get("fields", []):
        normalized_field_name = str(field_name or "").strip()
        if normalized_field_name and _DEDUP_FIELD_RE.match(normalized_field_name) and normalized_field_name not in normalized_fields:
            normalized_fields.append(normalized_field_name)

    condition = str(dedup_settings.get("condition") or "any").strip().lower()
    if condition not in {"all", "any"}:
        condition = "any"

    return {
        "strategy": strategy,
        "fields": normalized_fields,
        "condition": condition,
    }


def normalize_linked_dedup_settings(dedup_settings, entity_type: str = LINKED_COMPANY_CONTACT_ENTITY_TYPE) -> dict:
    linked_entity_ids = get_linked_entity_ids(entity_type)
    if isinstance(dedup_settings, dict) and any(isinstance(dedup_settings.get(linked_entity), dict) for linked_entity in linked_entity_ids):
        return {
            linked_entity: normalize_dedup_settings(dedup_settings.get(linked_entity, {}))
            for linked_entity in linked_entity_ids
        }

    shared_settings = normalize_dedup_settings(dedup_settings)
    linked_prefix_map = {
        linked_entity: str(prefix or "").strip().upper()
        for linked_entity, prefix in get_linked_entity_prefix_map(entity_type).items()
    }
    split_fields = {linked_entity: [] for linked_entity in linked_entity_ids}

    for field_name in shared_settings["fields"]:
        matched_linked_entity = None
        for linked_entity in linked_entity_ids:
            prefix = linked_prefix_map.get(linked_entity, "")
            if prefix and field_name.startswith(prefix):
                normalized_field_name = str(field_name[len(prefix):] or "").strip().upper()
                if normalized_field_name and _DEDUP_FIELD_RE.match(normalized_field_name):
                    split_fields[linked_entity].append(normalized_field_name)
                matched_linked_entity = linked_entity
                break

        if matched_linked_entity is not None:
            continue

        for linked_entity in linked_entity_ids:
            split_fields[linked_entity].append(field_name)

    return {
        linked_entity: {
            **shared_settings,
            "fields": split_fields[linked_entity],
        }
        for linked_entity in linked_entity_ids
    }


def normalize_entity_dedup_settings(entity_type: str, dedup_settings):
    if is_linked_import_entity_type(entity_type):
        return normalize_linked_dedup_settings(dedup_settings, entity_type=entity_type)
    return normalize_dedup_settings(dedup_settings)


def extract_dedup_lookup_value(value):
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue

            normalized_item_value = normalize_value(item.get("VALUE"))
            if normalized_item_value:
                return normalized_item_value

        return ""

    return normalize_value(value)


def _find_user_by_email(account, email: str):
    response = BitrixAPIRequest(
        bitrix_token=account,
        api_method="user.get",
        params={"filter": {"EMAIL": email}, "select": ["ID"]},
    )
    result = unwrap_bitrix_result(response)
    if isinstance(result, list) and result:
        return normalize_record_id(result[0].get("ID") or result[0].get("id"))
    return None


def _find_department_by_name(account, name: str):
    response = BitrixAPIRequest(
        bitrix_token=account,
        api_method="department.get",
        params={"filter": {"NAME": name}, "select": ["ID"]},
    )
    result = unwrap_bitrix_result(response)
    if isinstance(result, list) and result:
        return normalize_record_id(result[0].get("ID") or result[0].get("id"))
    return None


def _create_user(account, fields: dict):
    params = {**fields}
    params.setdefault("EXTRANET", "N")
    params.setdefault("ACTIVE", "Y")
    # Bitrix24 requires UF_DEPARTMENT for intranet users (EXTRANET=N)
    if not params.get("UF_DEPARTMENT"):
        params["UF_DEPARTMENT"] = 1
    try:
        req = account.client.user.add(params)
        result = req.result
        return normalize_record_id(result)
    except Exception as add_error:
        if not ("unknown error" in str(add_error).lower() and params.get("EMAIL")):
            raise
        # Bitrix24 returns "Unknown error." when email belongs to a deactivated (fired)
        # user. user.get without ACTIVE filter only returns active users — must search
        # specifically with ACTIVE:"N" to find deactivated accounts.
        try:
            existing = BitrixAPIRequest(
                bitrix_token=account,
                api_method="user.get",
                params={"filter": {"EMAIL": params["EMAIL"], "ACTIVE": "N"}, "select": ["ID"]},
            )
            result = unwrap_bitrix_result(existing)
            if isinstance(result, list) and result:
                user_id = normalize_record_id(result[0].get("ID") or result[0].get("id"))
                if user_id:
                    update_params = {k: v for k, v in params.items() if k != "EMAIL"}
                    update_params["ACTIVE"] = "Y"
                    BitrixAPIRequest(
                        bitrix_token=account,
                        api_method="user.update",
                        params={"id": user_id, **update_params},
                    )
                    return user_id
        except Exception:
            pass
        raise


def _update_user(account, record_id, fields: dict):
    BitrixAPIRequest(
        bitrix_token=account,
        api_method="user.update",
        params={"id": record_id, **fields},
    )


def _create_department(account, fields: dict):
    response = BitrixAPIRequest(
        bitrix_token=account,
        api_method="department.add",
        params=fields,
    )
    result = unwrap_bitrix_result(response)
    if isinstance(result, dict):
        return normalize_record_id(result.get("ID") or result.get("id") or result.get("result"))
    return normalize_record_id(result)


def _update_department(account, record_id, fields: dict):
    BitrixAPIRequest(
        bitrix_token=account,
        api_method="department.update",
        params={"id": record_id, **fields},
    )


def get_entity_scope(client, entity_type: str):
    if entity_type == "task":
        tasks_root = getattr(client, "tasks", None)
        task_scope = getattr(tasks_root, "task", None) or getattr(tasks_root, "tasks", None)
        if task_scope is None:
            raise ValueError("Unsupported entity type")
        return task_scope

    if entity_type == "task_checklist_item":
        return _resolve_task_child_scope(client, "checklistitem")

    crm_scope = getattr(client, "crm", None)
    entity_scopes = {
        "lead": getattr(crm_scope, "lead", None),
        "contact": getattr(crm_scope, "contact", None),
        "company": getattr(crm_scope, "company", None),
        "deal": getattr(crm_scope, "deal", None),
    }

    scope = entity_scopes.get(entity_type)
    if scope is None:
        raise ValueError("Unsupported entity type")

    return scope


def invoke_with_fallbacks(callers: list):
    last_type_error = None
    for caller in callers:
        try:
            return caller()
        except TypeError as error:
            last_type_error = error

    if last_type_error is not None:
        raise last_type_error

    raise ValueError("No Bitrix API call variants were provided")


def extract_record_id_from_list_response(response):
    result = unwrap_bitrix_result(response)

    if isinstance(result, dict):
        items = result.get("items")
        if not isinstance(items, list):
            items = result.get("result")
    else:
        items = result

    if not isinstance(items, list) or not items:
        return None

    first_item = items[0]
    if not isinstance(first_item, dict):
        return None

    record_id = first_item.get("ID") or first_item.get("id")
    if record_id is None:
        return None

    return normalize_record_id(record_id)


def find_record_by_filter(list_method, lookup_filter: dict):
    if not lookup_filter:
        return None

    response = invoke_with_fallbacks(
        [
            lambda: list_method(filter=lookup_filter, select=["ID"]),
            lambda: list_method(lookup_filter, ["ID"]),
            lambda: list_method(filter=lookup_filter),
        ]
    )
    return extract_record_id_from_list_response(response)


_DEDUP_FIELD_API_ALIASES = {"EXTERNAL_KEY": "XML_ID"}


def build_dedup_lookup_filter(row_payload: dict, dedup_settings: dict) -> tuple[dict, list[str], list[str]]:
    lookup_filter = {}
    matched_fields = []
    missing_fields = []

    for field_name in dedup_settings["fields"]:
        api_field_name = _DEDUP_FIELD_API_ALIASES.get(field_name, field_name)
        field_value = extract_dedup_lookup_value(
            row_payload.get(field_name) or row_payload.get(api_field_name)
        )
        if not field_value:
            missing_fields.append(field_name)
            continue
        lookup_filter[api_field_name] = field_value
        matched_fields.append(field_name)

    return lookup_filter, matched_fields, missing_fields


def _find_hr_existing_record(account, entity_type: str, row_payload: dict, dedup_settings: dict):
    if dedup_settings["strategy"] == "create" or not dedup_settings["fields"]:
        return None

    matched_fields = []
    record_id = None

    if entity_type == "user":
        email = extract_dedup_lookup_value(row_payload.get("EMAIL"))
        if email and "EMAIL" in dedup_settings["fields"]:
            record_id = _find_user_by_email(account, email)
            if record_id is not None:
                matched_fields = ["EMAIL"]

    elif entity_type == "department":
        name = extract_dedup_lookup_value(row_payload.get("NAME"))
        if name and "TITLE" in dedup_settings["fields"]:
            record_id = _find_department_by_name(account, name)
            if record_id is not None:
                matched_fields = ["NAME"]

    if record_id is None:
        return None

    return {
        "record_id": record_id,
        "duplicate_match_fields": matched_fields,
        "dedup_missing_fields": [],
    }


def _normalize_smart_process_dedup_settings(row_payload: dict, dedup_settings: dict) -> dict:
    # dedup fields arrive as UPPERCASE ("TITLE"), but smart process payload keys are camelCase ("title").
    # Map each dedup field name to the actual key present in row_payload (case-insensitive).
    payload_upper_map = {k.upper(): k for k in row_payload}
    normalized_fields = [payload_upper_map.get(f.upper(), f) for f in dedup_settings.get("fields", [])]
    return {**dedup_settings, "fields": normalized_fields}


def _find_smart_process_record_by_filter(account, entity_type_id: int, lookup_filter: dict):
    response = BitrixAPIRequest(
        bitrix_token=account,
        api_method="crm.item.list",
        params={
            "entityTypeId": entity_type_id,
            "filter": dict(lookup_filter or {}),
            "select": ["id"],
        },
    )
    return extract_record_id_from_list_response(response)


def _find_smart_process_existing_record(account, row_payload: dict, dedup_settings: dict, *, context: dict | None = None):
    smart_process_config = normalize_smart_process_entity_config((context or {}).get("entity_config"))
    entity_type_id = smart_process_config["entityTypeId"]
    sp_dedup_settings = _normalize_smart_process_dedup_settings(row_payload, dedup_settings)
    lookup_filter, matched_fields, missing_fields = build_dedup_lookup_filter(row_payload, sp_dedup_settings)
    dedup_missing_fields = missing_fields if matched_fields and missing_fields else []

    if not lookup_filter:
        return None

    condition = str(dedup_settings.get("condition") or "any")

    if condition == "all":
        record_id = _find_smart_process_record_by_filter(account, entity_type_id, lookup_filter)
        if record_id is None:
            if dedup_missing_fields:
                return {"dedup_missing_fields": dedup_missing_fields}
            return None
        return {
            "record_id": record_id,
            "duplicate_match_fields": matched_fields,
            "dedup_missing_fields": dedup_missing_fields,
        }

    for field_name, field_value in lookup_filter.items():
        record_id = _find_smart_process_record_by_filter(account, entity_type_id, {field_name: field_value})
        if record_id is not None:
            return {
                "record_id": record_id,
                "duplicate_match_fields": [field_name],
                "dedup_missing_fields": dedup_missing_fields,
            }

    if dedup_missing_fields:
        return {
            "dedup_missing_fields": dedup_missing_fields,
        }

    return None


def find_existing_record(account, entity_type: str, row_payload: dict, dedup_settings: dict, *, context: dict | None = None):
    if dedup_settings["strategy"] == "create" or not dedup_settings["fields"]:
        return None

    if entity_type in TASK_ENTITY_TYPES or entity_type in CRM_FILES_ENTITY_TYPES or entity_type in CRM_ACTIVITY_ENTITY_TYPES:
        return None

    if entity_type == SMART_PROCESS_ENTITY_TYPE:
        return _find_smart_process_existing_record(account, row_payload, dedup_settings, context=context)

    if entity_type in HR_ENTITY_TYPES:
        return _find_hr_existing_record(account, entity_type, row_payload, dedup_settings)

    # Special case: if "ID" is the only dedup field, use it directly as record_id (no API search needed)
    if dedup_settings["fields"] == ["ID"]:
        raw_id = extract_dedup_lookup_value(row_payload.get("ID"))
        record_id = normalize_record_id(raw_id) if raw_id else None
        if record_id is None:
            return None
        return {"record_id": record_id, "duplicate_match_fields": ["ID"], "dedup_missing_fields": []}

    scope = get_entity_scope(account.client, entity_type)
    list_method = getattr(scope, "list", None)
    if list_method is None:
        raise ValueError("Bitrix entity list method is unavailable")

    lookup_filter, matched_fields, missing_fields = build_dedup_lookup_filter(row_payload, dedup_settings)
    dedup_missing_fields = missing_fields if matched_fields and missing_fields else []

    if not lookup_filter:
        return None

    condition = str(dedup_settings.get("condition") or "any")

    if condition == "all":
        # All fields must match simultaneously (AND)
        record_id = find_record_by_filter(list_method, lookup_filter)
        if record_id is None:
            if dedup_missing_fields:
                return {"dedup_missing_fields": dedup_missing_fields}
            return None
        return {
            "record_id": record_id,
            "duplicate_match_fields": matched_fields,
            "dedup_missing_fields": dedup_missing_fields,
        }

    # condition == "any": match by each field independently, return first hit (OR)
    for field_name, field_value in lookup_filter.items():
        record_id = find_record_by_filter(list_method, {field_name: field_value})
        if record_id is not None:
            return {
                "record_id": record_id,
                "duplicate_match_fields": [field_name],
                "dedup_missing_fields": dedup_missing_fields,
            }

    if dedup_missing_fields:
        return {
            "dedup_missing_fields": dedup_missing_fields,
        }

    return None


def build_dedup_lookup_cache_key(entity_type: str, row_payload: dict, dedup_settings: dict, *, context: dict | None = None):
    if not isinstance(row_payload, dict) or not isinstance(dedup_settings, dict):
        return None

    normalized_entity_type = str(entity_type or "").strip().lower()
    strategy = str(dedup_settings.get("strategy") or "create").strip().lower()
    condition = str(dedup_settings.get("condition") or "any").strip().lower()
    fields = tuple(str(field_name or "").strip() for field_name in dedup_settings.get("fields", []))

    if normalized_entity_type == "user":
        return (
            normalized_entity_type,
            strategy,
            condition,
            fields,
            ("EMAIL", extract_dedup_lookup_value(row_payload.get("EMAIL"))),
        )

    if normalized_entity_type == "department":
        return (
            normalized_entity_type,
            strategy,
            condition,
            fields,
            ("NAME", extract_dedup_lookup_value(row_payload.get("NAME"))),
        )

    if fields == ("ID",):
        return (
            normalized_entity_type,
            strategy,
            condition,
            fields,
            ("ID", extract_dedup_lookup_value(row_payload.get("ID"))),
        )

    if normalized_entity_type == SMART_PROCESS_ENTITY_TYPE:
        smart_process_config = normalize_smart_process_entity_config((context or {}).get("entity_config"))
        sp_dedup_settings = _normalize_smart_process_dedup_settings(row_payload, dedup_settings)
        lookup_filter, matched_fields, missing_fields = build_dedup_lookup_filter(row_payload, sp_dedup_settings)
        return (
            normalized_entity_type,
            smart_process_config["entityTypeId"],
            strategy,
            condition,
            fields,
            tuple(sorted(lookup_filter.items())),
            tuple(matched_fields),
            tuple(missing_fields),
        )

    lookup_filter, matched_fields, missing_fields = build_dedup_lookup_filter(row_payload, dedup_settings)
    return (
        normalized_entity_type,
        strategy,
        condition,
        fields,
        tuple(sorted(lookup_filter.items())),
        tuple(matched_fields),
        tuple(missing_fields),
    )


def find_existing_record_cached(account, entity_type: str, row_payload: dict, dedup_settings: dict, *, cache=None, context: dict | None = None):
    cache_key = build_dedup_lookup_cache_key(entity_type, row_payload, dedup_settings, context=context)
    if not isinstance(cache, dict) or cache_key is None:
        return find_existing_record(account, entity_type, row_payload, dedup_settings, context=context)

    if cache_key not in cache:
        cache[cache_key] = find_existing_record(account, entity_type, row_payload, dedup_settings, context=context)

    return cache[cache_key]


def _warm_dedup_cache(
    account,
    entity_type: str,
    rows: list,
    row_numbers: list,
    columns: list,
    data_start_row: int,
    mapping: dict,
    fields: list,
    normalized_dedup_settings: dict,
    cache: dict,
    user_resolver,
    default_field_values: dict | None = None,
    context: dict | None = None,
    warm_progress_callback=None,
) -> None:
    """Pre-warm dedup lookup cache using batch API calls before the main row loop.

    Converts N_rows × N_fields sequential API calls into ceil(N_rows×N_fields / 50)
    batch requests, giving up to 50x speedup for dedup-heavy imports.
    """
    strategy = normalized_dedup_settings.get("strategy", "create")
    dedup_fields = normalized_dedup_settings.get("fields", [])

    if strategy == "create" or not dedup_fields:
        return
    if entity_type in TASK_ENTITY_TYPES or entity_type in CRM_FILES_ENTITY_TYPES or entity_type in CRM_ACTIVITY_ENTITY_TYPES:
        return
    if entity_type in HR_ENTITY_TYPES or dedup_fields == ["ID"] or entity_type == SMART_PROCESS_ENTITY_TYPE:
        return

    api_method = _CRM_BATCH_LIST_METHODS.get(entity_type)
    if not api_method:
        return
    extra_params = {}
    select_param = ["ID"]

    condition = str(normalized_dedup_settings.get("condition") or "any")

    # Build row data: payload → cache key → dedup filter for every valid row
    row_data = []  # [(cache_key, lookup_filter, matched_fields, missing_fields), ...]
    for row_index, row_number in enumerate(row_numbers):
        if row_number < data_start_row:
            continue
        row = rows[row_index] if row_index < len(rows) else []
        if not row_has_values(row):
            continue
        try:
            row_payload = build_row_payload(
                row, columns, mapping, fields,
                account=account,
                user_resolver=user_resolver,
                default_field_values=default_field_values,
            )
        except Exception:
            continue
        cache_key = build_dedup_lookup_cache_key(entity_type, row_payload, normalized_dedup_settings, context=context)
        if cache_key is None or cache_key in cache:
            continue
        lookup_filter, matched_fields, missing_fields = build_dedup_lookup_filter(row_payload, normalized_dedup_settings)
        row_data.append((cache_key, lookup_filter, matched_fields, missing_fields))

    if not row_data:
        return

    # Build batch items list and per-key metadata
    pending = []   # [(batch_key, filter_dict), ...]
    key_meta = {}  # batch_key → (cache_key, field_name_or_None, matched_fields, dedup_missing)

    for rd_idx, (cache_key, lookup_filter, matched_fields, missing_fields) in enumerate(row_data):
        dedup_missing = missing_fields if matched_fields and missing_fields else []
        if not lookup_filter:
            cache[cache_key] = {"dedup_missing_fields": dedup_missing} if dedup_missing else None
            continue
        if condition == "all":
            bkey = str(rd_idx)
            pending.append((bkey, lookup_filter))
            key_meta[bkey] = (cache_key, None, matched_fields, dedup_missing)
        else:
            for f_idx, (field_name, field_value) in enumerate(lookup_filter.items()):
                bkey = f"{rd_idx}_{f_idx}"
                pending.append((bkey, {field_name: field_value}))
                key_meta[bkey] = (cache_key, field_name, matched_fields, dedup_missing)

    # For "any": accumulate all field results per row before deciding
    any_field_results: dict = {}  # cache_key → {field_name: record_id_or_None}

    total_batches = max(1, (len(pending) + BATCH_SIZE - 1) // BATCH_SIZE)
    for batch_start in range(0, len(pending), BATCH_SIZE):
        if batch_start > 0:
            _sleep_if_configured(BITRIX_BATCH_DELAY)
        chunk = pending[batch_start:batch_start + BATCH_SIZE]
        batch_requests = {
            bkey: BitrixAPIRequest(
                bitrix_token=account,
                api_method=api_method,
                params={"filter": filter_dict, "select": select_param, **extra_params},
            )
            for bkey, filter_dict in chunk
        }
        try:
            response = _bitrix_retry(lambda br=batch_requests: BitrixAPIBatchRequest(
                bitrix_token=account,
                bitrix_api_requests=br,
                halt=False,
            ))
            raw_results = _normalize_batch_collection(response.result.result)
        except Exception:
            return
        if callable(warm_progress_callback):
            done_n = batch_start // BATCH_SIZE + 1
            warm_progress_callback(done=done_n, total=total_batches)
        for bkey, _ in chunk:
            cache_key, field_name, matched_fields, dedup_missing = key_meta[bkey]
            raw = raw_results.get(bkey)
            record_id = extract_record_id_from_list_response(raw) if raw is not None else None

            if condition == "all":
                if record_id is not None:
                    cache[cache_key] = {
                        "record_id": record_id,
                        "duplicate_match_fields": matched_fields,
                        "dedup_missing_fields": dedup_missing,
                    }
                elif dedup_missing:
                    cache[cache_key] = {"dedup_missing_fields": dedup_missing}
                else:
                    cache[cache_key] = None
            else:
                if cache_key not in any_field_results:
                    any_field_results[cache_key] = {}
                any_field_results[cache_key][field_name] = record_id

    # For "any": pick first matching field (preserving lookup_filter key order)
    if condition == "any":
        for cache_key, lookup_filter, matched_fields, missing_fields in row_data:
            if cache_key in cache:
                continue
            dedup_missing = missing_fields if matched_fields and missing_fields else []
            field_results = any_field_results.get(cache_key, {})
            found = None
            for field_name in lookup_filter:
                record_id = field_results.get(field_name)
                if record_id is not None:
                    found = {
                        "record_id": record_id,
                        "duplicate_match_fields": [field_name],
                        "dedup_missing_fields": dedup_missing,
                    }
                    break
            cache[cache_key] = found if found is not None else ({"dedup_missing_fields": dedup_missing} if dedup_missing else None)


def filter_dedup_settings_for_payload(dedup_settings: dict, row_payload: dict) -> dict:
    payload_keys = {str(field_id) for field_id in (row_payload or {}).keys()}
    return {
        "strategy": str(dedup_settings.get("strategy") or "create"),
        "condition": str(dedup_settings.get("condition") or "any"),
        "fields": [
            str(field_name)
            for field_name in dedup_settings.get("fields", [])
            if str(field_name) in payload_keys
        ],
    }


def build_linked_result_meta(match: dict | None) -> dict:
    if not isinstance(match, dict):
        return {}

    result_meta = {}
    duplicate_match_fields = match.get("duplicate_match_fields", [])
    dedup_missing_fields = match.get("dedup_missing_fields", [])
    if duplicate_match_fields:
        result_meta["duplicate_match_fields"] = duplicate_match_fields
    if dedup_missing_fields:
        result_meta["dedup_missing_fields"] = dedup_missing_fields
    return result_meta


def resolve_linked_record_action(account, entity_type: str, row_payload: dict, dedup_settings: dict) -> dict:
    filtered_dedup_settings = filter_dedup_settings_for_payload(dedup_settings, row_payload)
    existing_record_match = find_existing_record(account, entity_type, row_payload, filtered_dedup_settings)
    existing_record_id = existing_record_match.get("record_id") if isinstance(existing_record_match, dict) else None

    if existing_record_id is None:
        return {
            "mode": "create",
            "record_id": None,
            "meta": build_linked_result_meta(existing_record_match),
        }

    strategy = filtered_dedup_settings.get("strategy")
    if strategy == "update":
        mode = "update"
    elif strategy in ("skip", "ask"):
        mode = "reuse"
    else:
        mode = "create"

    return {
        "mode": mode,
        "record_id": existing_record_id,
        "meta": build_linked_result_meta(existing_record_match),
    }


def resolve_linked_record_action_with_decision(
    account,
    entity_type: str,
    row_payload: dict,
    dedup_settings: dict,
    row_decision: str = "",
    find_existing_record_fn=None,
) -> dict:
    filtered_dedup_settings = filter_dedup_settings_for_payload(dedup_settings, row_payload)
    lookup_fn = find_existing_record_fn if callable(find_existing_record_fn) else find_existing_record
    existing_record_match = lookup_fn(account, entity_type, row_payload, filtered_dedup_settings)
    existing_record_id = existing_record_match.get("record_id") if isinstance(existing_record_match, dict) else None

    if existing_record_id is None:
        return {
            "mode": "create",
            "record_id": None,
            "meta": build_linked_result_meta(existing_record_match),
        }

    strategy = str(filtered_dedup_settings.get("strategy") or "create").strip().lower()
    normalized_row_decision = str(row_decision or "").strip().lower()
    if normalized_row_decision not in {"create", "update", "skip"}:
        normalized_row_decision = ""

    if strategy == "update":
        mode = "update"
    elif strategy == "skip":
        mode = "reuse"
    elif strategy == "ask":
        if normalized_row_decision == "create":
            mode = "create"
        elif normalized_row_decision == "update":
            mode = "update"
        elif normalized_row_decision == "skip":
            mode = "skip_row"
        else:
            mode = "pending_decision"
    else:
        mode = "create"

    return {
        "mode": mode,
        "record_id": existing_record_id,
        "meta": build_linked_result_meta(existing_record_match),
    }


def build_linked_duplicate_decision_summary(linked_actions: dict, entity_type: str) -> dict:
    linked_entity_labels = {
        "company": "Компания",
        "contact": "Контакт",
        "deal": "Сделка",
    }
    linked_prefix_map = get_linked_entity_prefix_map(entity_type)
    linked_meta = {}
    record_labels = []
    duplicate_match_fields = []
    dedup_missing_fields = []
    seen_record_labels = set()
    seen_duplicate_fields = set()
    seen_missing_fields = set()

    for linked_entity in get_linked_entity_ids(entity_type):
        linked_action = linked_actions.get(linked_entity, {})
        if not isinstance(linked_action, dict):
            continue

        meta = linked_action.get("meta", {})

        record_id = normalize_record_id(linked_action.get("record_id")) or linked_action.get("record_id")
        linked_entity_meta = dict(meta) if isinstance(meta, dict) else {}
        if linked_entity_meta:
            linked_meta[linked_entity] = linked_entity_meta

        if record_id is not None and (
            linked_action.get("mode") in {"pending_decision", "skip_row"}
            or (isinstance(meta, dict) and meta.get("duplicate_match_fields"))
        ):
            record_label = f"{linked_entity_labels.get(linked_entity, linked_entity)} {record_id}"
            if record_label not in seen_record_labels:
                seen_record_labels.add(record_label)
                record_labels.append(record_label)

        prefix = str(linked_prefix_map.get(linked_entity) or "")
        for field_name in meta.get("duplicate_match_fields", []) if isinstance(meta, dict) else []:
            normalized_field_name = str(field_name or "").strip()
            if not normalized_field_name:
                continue
            prefixed_field_name = f"{prefix}{normalized_field_name}" if prefix else normalized_field_name
            if prefixed_field_name in seen_duplicate_fields:
                continue
            seen_duplicate_fields.add(prefixed_field_name)
            duplicate_match_fields.append(prefixed_field_name)

        for field_name in meta.get("dedup_missing_fields", []) if isinstance(meta, dict) else []:
            normalized_field_name = str(field_name or "").strip()
            if not normalized_field_name:
                continue
            prefixed_field_name = f"{prefix}{normalized_field_name}" if prefix else normalized_field_name
            if prefixed_field_name in seen_missing_fields:
                continue
            seen_missing_fields.add(prefixed_field_name)
            dedup_missing_fields.append(prefixed_field_name)

    result = {}
    if record_labels:
        result["record_id"] = " · ".join(record_labels)
    if duplicate_match_fields:
        result["duplicate_match_fields"] = duplicate_match_fields
    if dedup_missing_fields:
        result["dedup_missing_fields"] = dedup_missing_fields
    if linked_meta:
        result["linked"] = linked_meta
    return result


def resolve_linked_row_decision(per_row_decisions: dict | None, row_number: int | str, linked_entity_type: str) -> str:
    if not isinstance(per_row_decisions, dict):
        return ""

    raw_decision = per_row_decisions.get(str(row_number))
    normalized_entity_type = str(linked_entity_type or "").strip().lower()
    if isinstance(raw_decision, dict):
        entity_decision = str(raw_decision.get(normalized_entity_type, "")).strip().lower()
        return entity_decision if entity_decision in {"create", "update", "skip"} else ""

    normalized_decision = str(raw_decision or "").strip().lower()
    return normalized_decision if normalized_decision in {"create", "update", "skip"} else ""


def build_linked_result_fields(linked_payload: dict, entity_type: str = LINKED_COMPANY_CONTACT_ENTITY_TYPE) -> dict:
    flattened_fields = {}
    linked_entity_prefixes = get_linked_entity_prefix_map(entity_type)

    for linked_entity, prefix in linked_entity_prefixes.items():
        entity_payload = linked_payload.get(linked_entity, {})
        if not isinstance(entity_payload, dict):
            continue

        for field_id, value in entity_payload.items():
            flattened_fields[f"{prefix}{field_id}"] = value

    return flattened_fields


def extract_linked_display_value(value) -> str:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                normalized_item_value = normalize_value(item.get("VALUE"))
                if normalized_item_value:
                    return normalized_item_value
            else:
                normalized_item_value = normalize_value(item)
                if normalized_item_value:
                    return normalized_item_value
        return ""

    return normalize_value(value)


def build_linked_record_title(linked_entity: str, row_payload: dict) -> str:
    if linked_entity == "company":
        return normalize_value(row_payload.get("TITLE"))

    if linked_entity == "deal":
        return normalize_value(row_payload.get("TITLE"))

    if linked_entity == "contact":
        parts = [
            normalize_value(row_payload.get("NAME")),
            normalize_value(row_payload.get("LAST_NAME")),
        ]
        full_name = " ".join(part for part in parts if part).strip()
        if full_name:
            return full_name

        for fallback_field in ("EMAIL", "PHONE"):
            fallback_value = extract_linked_display_value(row_payload.get(fallback_field))
            if fallback_value:
                return fallback_value

    return ""


def build_linked_record_result(linked_entity: str, row_payload: dict, record_id, action_mode: str) -> dict | None:
    normalized_record_id = normalize_record_id(record_id)
    title = build_linked_record_title(linked_entity, row_payload)
    if normalized_record_id is None and not title:
        return None

    status_by_mode = {
        "create": "created",
        "update": "updated",
        "reuse": "existing",
        "skip_payload": "skipped",
        "cached": "existing",
    }

    return {
        "id": normalized_record_id,
        "title": title,
        "status": status_by_mode.get(action_mode, action_mode),
    }


_CRM_MULTIVALUE_ENTITY_TYPES = {"lead", "contact", "company"}

_CRM_GET_METHOD = {
    "lead": "crm.lead.get",
    "contact": "crm.contact.get",
    "company": "crm.company.get",
}


def _fetch_existing_multivalue_fields(account, entity_type: str, record_id, field_ids: list) -> dict:
    api_method = _CRM_GET_METHOD.get(entity_type)
    if not api_method:
        return {}
    try:
        result = BitrixAPIRequest(
            bitrix_token=account,
            api_method=api_method,
            params={"ID": record_id},
        ).result
        if not isinstance(result, dict):
            return {}
        return {fid: result[fid] for fid in field_ids if isinstance(result.get(fid), list)}
    except Exception:
        return {}


def _merge_multivalue_update_payload(existing_by_field: dict, update_payload: dict) -> dict:
    """
    For each multi-value field in update_payload, reuse existing entry IDs so Bitrix24
    updates entries in place rather than appending new ones.
    Existing entries of types NOT present in update_payload are left untouched.
    """
    if not existing_by_field:
        return update_payload
    merged = dict(update_payload)
    for field_id, new_values in update_payload.items():
        if field_id not in BITRIX_MULTIFIELD_IDS:
            continue
        if not isinstance(new_values, list):
            continue
        existing_entries = existing_by_field.get(field_id)
        if not isinstance(existing_entries, list) or not existing_entries:
            continue
        existing_by_type: dict[str, list] = {}
        for entry in existing_entries:
            vtype = str(entry.get("VALUE_TYPE") or "WORK").upper()
            existing_by_type.setdefault(vtype, []).append(entry)
        merged_values = []
        used_ids: set = set()
        for new_item in new_values:
            vtype = str(new_item.get("VALUE_TYPE") or "WORK").upper()
            candidate = next(
                (e for e in existing_by_type.get(vtype, []) if e.get("ID") and e["ID"] not in used_ids),
                None,
            )
            if candidate:
                used_ids.add(candidate["ID"])
                merged_values.append({"ID": candidate["ID"], "VALUE": new_item.get("VALUE", ""), "VALUE_TYPE": vtype})
            else:
                merged_values.append(new_item)
        merged[field_id] = merged_values
    return merged


def update_entity_record(account, entity_type: str, record_id, fields: dict):
    if entity_type in TASK_ENTITY_TYPES or entity_type in CRM_FILES_ENTITY_TYPES or entity_type in CRM_ACTIVITY_ENTITY_TYPES:
        raise ValueError("Update is not supported for this entity type")

    if entity_type == SMART_PROCESS_ENTITY_TYPE:
        raise ValueError("Smart process update requires entity context")

    if entity_type == "user":
        _update_user(account, record_id, fields)
        return True

    if entity_type == "department":
        _update_department(account, record_id, fields)
        return True

    if entity_type in _CRM_MULTIVALUE_ENTITY_TYPES:
        multivalue_field_ids = [f for f in BITRIX_MULTIFIELD_IDS if f in fields]
        if multivalue_field_ids:
            existing = _fetch_existing_multivalue_fields(account, entity_type, record_id, multivalue_field_ids)
            fields = _merge_multivalue_update_payload(existing, fields)

    scope = get_entity_scope(account.client, entity_type)
    update_method = getattr(scope, "update", None)
    if update_method is None:
        raise ValueError("Bitrix entity update method is unavailable")

    response = invoke_with_fallbacks(
        [
            lambda: update_method(record_id, fields),
            lambda: update_method(id=record_id, fields=fields),
            lambda: update_method(record_id, fields=fields),
        ]
    )
    return unwrap_bitrix_result(response)


def update_smart_process_record(account, entity_config: dict, record_id, fields: dict):
    smart_process_config = normalize_smart_process_entity_config(entity_config)
    response = BitrixAPIRequest(
        bitrix_token=account,
        api_method="crm.item.update",
        params={
            "entityTypeId": smart_process_config["entityTypeId"],
            "id": record_id,
            "fields": dict(fields),
        },
    )
    return unwrap_bitrix_result(response)


def _resolve_task_child_scope(client, attribute_name: str):
    for tasks_root_name in ("tasks", "task"):
        tasks_root = getattr(client, tasks_root_name, None)
        if tasks_root is None:
            continue
        scope = getattr(tasks_root, attribute_name, None)
        if scope is not None:
            return scope
    return None


def _extract_task_child_parent_id(fields: dict) -> int:
    return _resolve_task_reference_id(fields.get("TASK_ID"), "TASK_ID")


def _resolve_task_reference_id(value, field_name: str, *, task_resolver: BitrixTaskResolver | None = None) -> int:
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")

    if isinstance(value, int):
        if value > 0:
            return value
        raise ValueError(f"{field_name} must be a positive integer")

    normalized_value = normalize_value(value)
    if not normalized_value:
        raise ValueError(f"{field_name} is required")

    try:
        resolved_id = int(normalized_value)
    except (TypeError, ValueError):
        resolved_id = None

    if resolved_id is not None:
        if resolved_id > 0:
            return resolved_id
        raise ValueError(f"{field_name} must be a positive integer")

    if task_resolver is not None:
        resolved_id = task_resolver.resolve(normalized_value)
        if resolved_id is not None:
            return resolved_id

    raise ValueError(f"{field_name} must be a positive integer or valid Bitrix task reference")


def _extract_checklist_item_id(result) -> int:
    if isinstance(result, dict):
        checklist_item = result.get("checkListItem")
        if isinstance(checklist_item, dict):
            return normalize_record_id(checklist_item.get("id") or checklist_item.get("ID"))
        return normalize_record_id(result.get("id") or result.get("ID") or result.get("result"))
    return normalize_record_id(result)


def _extract_task_comment_message_id(result):
    if isinstance(result, dict):
        message_id = result.get("id") or result.get("ID")
        if message_id is not None:
            return normalize_record_id(message_id)

        nested_result = result.get("result")
        if isinstance(nested_result, dict):
            nested_message_id = (
                nested_result.get("id")
                or nested_result.get("ID")
                or nested_result.get("messageId")
                or nested_result.get("MESSAGE_ID")
            )
            if nested_message_id is not None:
                return normalize_record_id(nested_message_id)

        return None

    return normalize_record_id(result)


def _get_or_create_checklist_group(account, task_id: int, context: dict | None) -> int:
    cache = (context or {}).get("checklist_group_cache")
    if cache is not None and task_id in cache:
        return cache[task_id]

    response = BitrixAPIRequest(
        bitrix_token=account,
        api_method="tasks.task.checklist.add",
        params={"taskId": task_id, "fields": {"TITLE": "Чек-лист", "PARENT_ID": 0}},
    )
    group_id = _extract_checklist_item_id(unwrap_bitrix_result(response))

    if cache is not None:
        cache[task_id] = group_id

    return group_id


def create_entity_record(account, entity_type: str, fields: dict, *, context: dict | None = None):
    task_resolver = BitrixTaskResolver(account)

    if entity_type in CRM_FILES_ENTITY_TYPES:
        raw_id = normalize_value(fields.get("ID"))
        if not raw_id:
            raise ValueError("ID is required for CRM file attachment")
        try:
            record_id = int(raw_id)
            if record_id <= 0:
                raise ValueError()
        except (TypeError, ValueError):
            raise ValueError(f"ID must be a positive integer, got: {raw_id!r}")

        file_url = normalize_value(fields.get("FILE_URL"))
        if not file_url:
            raise ValueError("FILE_URL is required for CRM file attachment")

        field_id = normalize_value(fields.get("FIELD_ID"))
        if not field_id:
            raise ValueError("FIELD_ID is required for CRM file attachment")

        download_result = download_attachment_source(file_url)
        file_name = (
            normalize_value(fields.get("FILE_NAME"))
            or normalize_value(download_result.get("file_name"))
            or "attachment.bin"
        )
        attach_file_to_crm_entity(
            account,
            entity_type=entity_type,
            record_id=record_id,
            field_id=field_id,
            file_name=file_name,
            content=download_result.get("content") or b"",
        )
        return record_id

    if entity_type == "task_attachment":
        task_id = _resolve_task_reference_id(fields.get("TASK_ID"), "TASK_ID", task_resolver=task_resolver)
        file_url = normalize_value(fields.get("FILE_URL"))
        if not file_url:
            raise ValueError("FILE_URL is required for task attachments")

        download_result = download_attachment_source(file_url)
        file_name = normalize_value(fields.get("FILE_NAME")) or normalize_value(download_result.get("file_name")) or "attachment.bin"
        attachment_result = attach_file_to_task(
            account,
            task_id=task_id,
            file_name=file_name,
            content=download_result.get("content") or b"",
            content_type=normalize_value(download_result.get("content_type")) or "application/octet-stream",
        )
        attachment_payload = unwrap_bitrix_result(attachment_result)
        if isinstance(attachment_payload, dict):
            attachment_id = (
                attachment_payload.get("attachment_id")
                or attachment_payload.get("ID")
                or attachment_payload.get("id")
                or attachment_payload.get("result")
            )
            if attachment_id is not None:
                return normalize_record_id(attachment_id)

        return normalize_record_id(attachment_payload)

    if entity_type == "task":
        task_fields = dict(fields)
        if "PARENT_ID" in task_fields:
            task_fields["PARENT_ID"] = _resolve_task_reference_id(
                task_fields.get("PARENT_ID"), "PARENT_ID", task_resolver=task_resolver
            )
        client = getattr(account, "client", None)
        tasks_root = getattr(client, "tasks", None)
        task_scope = getattr(tasks_root, "task", None) or getattr(tasks_root, "tasks", None)
        add_method = getattr(task_scope, "add", None)
        if add_method is not None:
            response = invoke_with_fallbacks(
                [
                    lambda: add_method(task_fields),
                    lambda: add_method(fields=task_fields),
                ]
            )
        else:
            response = BitrixAPIRequest(
                bitrix_token=account,
                api_method="tasks.task.add",
                params={"fields": task_fields},
            )
        result = unwrap_bitrix_result(response)
        if isinstance(result, dict):
            task_data = result.get("task") or result
            return normalize_record_id(task_data.get("id") or task_data.get("ID"))
        return normalize_record_id(result)

    if entity_type in TASK_CHILD_ENTITY_TYPES:
        parent_task_id = _resolve_task_reference_id(fields.get("TASK_ID"), "TASK_ID", task_resolver=task_resolver)
        child_fields = {
            field_id: value
            for field_id, value in fields.items()
            if field_id != "TASK_ID"
        }
        if entity_type == "task_checklist_item":
            checklist_scope = get_entity_scope(account.client, "task_checklist_item")
            add_method = getattr(checklist_scope, "add", None)
            if add_method is not None:
                response = invoke_with_fallbacks(
                    [
                        lambda: add_method(parent_task_id, child_fields),
                        lambda: add_method(taskId=parent_task_id, fields=child_fields),
                        lambda: add_method(task_id=parent_task_id, fields=child_fields),
                    ]
                )
            else:
                child_fields["PARENT_ID"] = _get_or_create_checklist_group(account, parent_task_id, context)
                response = BitrixAPIRequest(
                    bitrix_token=account,
                    api_method=TASK_CHILD_API_METHODS[entity_type],
                    params={"taskId": parent_task_id, "fields": child_fields},
                )
            return _extract_checklist_item_id(unwrap_bitrix_result(response))

        if entity_type == "task_comment":
            comment_text = normalize_value(child_fields.get("POST_MESSAGE"))
            author_id = normalize_record_id(child_fields.get("AUTHOR_ID"))

            if author_id is not None:
                response = BitrixAPIRequest(
                    bitrix_token=account,
                    api_method="task.commentitem.add",
                    params={
                        "TASKID": parent_task_id,
                        "FIELDS": {
                            "POST_MESSAGE": comment_text,
                            "AUTHOR_ID": author_id,
                        },
                    },
                )
                return normalize_record_id(unwrap_bitrix_result(response))

            response = BitrixAPIRequest(
                bitrix_token=account,
                api_method=TASK_CHILD_API_METHODS[entity_type],
                params={
                    "fields": {
                        "taskId": parent_task_id,
                        "text": comment_text,
                    }
                },
            )
            return _extract_task_comment_message_id(unwrap_bitrix_result(response))

    if entity_type == "crm_activity":
        owner_type_id = normalize_value(fields.get("OWNER_TYPE_ID"))
        owner_id = normalize_value(fields.get("OWNER_ID"))
        type_id = normalize_value(fields.get("TYPE_ID"))
        subject = normalize_value(fields.get("SUBJECT"))
        if not owner_type_id:
            raise ValueError("OWNER_TYPE_ID обязателен для активности CRM")
        if not owner_id:
            raise ValueError("OWNER_ID обязателен для активности CRM")
        if not type_id:
            raise ValueError("TYPE_ID обязателен для активности CRM")
        if not subject:
            raise ValueError("SUBJECT обязателен для активности CRM")

        activity_fields = {
            "OWNER_TYPE_ID": int(owner_type_id),
            "OWNER_ID": int(owner_id),
            "TYPE_ID": int(type_id),
            "SUBJECT": subject,
            # Bitrix24 requires COMMUNICATIONS for activities; calls/emails also need VALUE.
            "COMMUNICATIONS": build_crm_activity_communications(fields),
        }
        _INTEGER_ACTIVITY_FIELDS = {"RESPONSIBLE_ID", "DIRECTION", "STATUS", "PRIORITY"}
        for field_key in ("DESCRIPTION", "START_TIME", "END_TIME", "DEADLINE",
                          "RESPONSIBLE_ID", "DIRECTION", "STATUS", "PRIORITY"):
            val = normalize_value(fields.get(field_key))
            if val:
                activity_fields[field_key] = int(val) if field_key in _INTEGER_ACTIVITY_FIELDS else val

        response = BitrixAPIRequest(
            bitrix_token=account,
            api_method="crm.activity.add",
            params={"fields": activity_fields},
        )
        return normalize_record_id(unwrap_bitrix_result(response))

    if entity_type == "crm_note":
        entity_type_val = normalize_value(fields.get("ENTITY_TYPE"))
        entity_id = normalize_value(fields.get("ENTITY_ID"))
        comment = normalize_value(fields.get("COMMENT"))
        if not entity_type_val:
            raise ValueError("ENTITY_TYPE обязателен для заметки CRM")
        if not entity_id:
            raise ValueError("ENTITY_ID обязателен для заметки CRM")
        if not comment:
            raise ValueError("COMMENT обязателен для заметки CRM")

        note_fields = {
            "ENTITY_TYPE": entity_type_val.upper(),
            "ENTITY_ID": int(entity_id),
            "COMMENT": comment,
        }
        created_time = normalize_value(fields.get("CREATED_TIME"))
        if created_time:
            note_fields["CREATED_TIME"] = created_time

        response = BitrixAPIRequest(
            bitrix_token=account,
            api_method="crm.timeline.comment.add",
            params={"fields": note_fields},
        )
        return normalize_record_id(unwrap_bitrix_result(response))

    if entity_type == SMART_PROCESS_ENTITY_TYPE:
        smart_process_config = normalize_smart_process_entity_config((context or {}).get("entity_config"))
        response = BitrixAPIRequest(
            bitrix_token=account,
            api_method="crm.item.add",
            params={
                "entityTypeId": smart_process_config["entityTypeId"],
                "fields": dict(fields),
            },
        )
        result = unwrap_bitrix_result(response)
        if isinstance(result, dict):
            item = result.get("item")
            if isinstance(item, dict):
                return normalize_record_id(item.get("id") or item.get("ID"))
            return normalize_record_id(result.get("id") or result.get("ID") or result.get("result"))
        return normalize_record_id(result)

    if entity_type == "user":
        return _create_user(account, fields)

    if entity_type == "department":
        return _create_department(account, fields)

    scope = get_entity_scope(account.client, entity_type)

    return unwrap_bitrix_result(scope.add(fields))


def execute_linked_dry_run(
    *,
    account,
    entity_type: str = LINKED_COMPANY_CONTACT_ENTITY_TYPE,
    rows: list[list],
    row_numbers: list[int],
    columns: list[str],
    data_start_row: int,
    mapping: dict,
    validation_summary: dict,
    fields: list[dict],
    dedup_settings: dict,
    should_cancel=None,
    default_field_values: dict | None = None,
    progress_callback=None,
    warm_progress_callback=None,
) -> dict:
    invalid_row_numbers = get_invalid_row_numbers(validation_summary)
    user_resolver = BitrixUserResolver(account)
    dedup_lookup_cache: dict[tuple, dict | None] = {}
    parent_entity_type = get_linked_parent_entity_type(entity_type)
    child_entity_type = get_linked_child_entity_type(entity_type)

    _linked_entity_types = [parent_entity_type, child_entity_type]
    _batch_size = BATCH_SIZE
    _total_batches = sum(
        max(1, (len(row_numbers) + _batch_size - 1) // _batch_size)
        for _ in _linked_entity_types
    )
    _done_batches = [0]

    def _linked_warm_callback(*, done, total):
        if callable(warm_progress_callback):
            _done_batches[0] += 1
            warm_progress_callback(done=_done_batches[0], total=_total_batches)

    for _linked_et in _linked_entity_types:
        _warm_dedup_cache(
            account=account,
            entity_type=_linked_et,
            rows=rows,
            row_numbers=row_numbers,
            columns=columns,
            data_start_row=data_start_row,
            mapping=mapping,
            fields=fields,
            normalized_dedup_settings=normalize_dedup_settings(dedup_settings.get(_linked_et, {})),
            cache=dedup_lookup_cache,
            user_resolver=user_resolver,
            default_field_values=default_field_values,
            warm_progress_callback=_linked_warm_callback,
        )
    checked_rows = 0
    ready_rows = 0
    ready_create_rows = 0
    ready_update_rows = 0
    skipped_rows = 0
    pending_decision_rows = 0
    cancelled_rows = 0
    results = []
    was_cancelled = False
    parent_ext_key_cache: dict[str, str] = {}

    def _find_existing_linked_record(account, linked_entity_type: str, row_payload: dict, linked_dedup_settings: dict):
        return find_existing_record_cached(
            account,
            linked_entity_type,
            row_payload,
            linked_dedup_settings,
            cache=dedup_lookup_cache,
        )

    for row_index, row_number in enumerate(row_numbers):
        if row_number < data_start_row:
            continue

        row = rows[row_index] if row_index < len(rows) else []
        if not row_has_values(row):
            continue

        if callable(should_cancel) and should_cancel():
            was_cancelled = True
            for remaining_index in range(row_index, len(row_numbers)):
                remaining_row_number = row_numbers[remaining_index]
                if remaining_row_number < data_start_row:
                    continue

                remaining_row = rows[remaining_index] if remaining_index < len(rows) else []
                if not row_has_values(remaining_row):
                    continue

                cancelled_rows += 1
                results.append(
                    {
                        "row_number": remaining_row_number,
                        "status": "cancelled",
                        "error": "Dry run was cancelled before row execution",
                    }
                )
            break

        checked_rows += 1

        if row_number in invalid_row_numbers:
            skipped_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "skipped",
                    "error": "Row has validation issues",
                }
            )
            _report_dry_run_progress(
                progress_callback,
                checked_rows=checked_rows,
                ready_rows=ready_rows,
                skipped_rows=skipped_rows,
                pending_decision_rows=pending_decision_rows,
            )
            continue

        linked_payload = build_linked_row_payload(
            row,
            columns,
            mapping,
            fields,
            entity_type=entity_type,
            account=account,
            user_resolver=user_resolver,
            default_field_values=default_field_values,
        )

        raw_parent_payload = linked_payload.get(parent_entity_type, {})
        if raw_parent_payload:
            parent_payload_for_resolve = dict(raw_parent_payload)
            ext_key = str(parent_payload_for_resolve.pop("EXTERNAL_KEY", "") or "").strip()
            if ext_key:
                parent_payload_for_resolve["XML_ID"] = ext_key
        else:
            parent_payload_for_resolve = {}
            ext_key = ""

        if ext_key and ext_key in parent_ext_key_cache:
            parent_action: dict = parent_ext_key_cache[ext_key]
        elif parent_payload_for_resolve:
            parent_action = resolve_linked_record_action_with_decision(
                account,
                parent_entity_type,
                parent_payload_for_resolve,
                dedup_settings.get(parent_entity_type, {}),
                "",
                find_existing_record_fn=_find_existing_linked_record,
            )
            if ext_key:
                parent_ext_key_cache[ext_key] = parent_action
        else:
            parent_action = {"mode": "skip_payload", "record_id": None, "meta": {}}

        child_action = resolve_linked_record_action_with_decision(
            account,
            child_entity_type,
            linked_payload.get(child_entity_type, {}),
            dedup_settings.get(child_entity_type, {}),
            "",
            find_existing_record_fn=_find_existing_linked_record,
        ) if linked_payload.get(child_entity_type) else {"mode": "skip_payload", "record_id": None, "meta": {}}

        linked_actions = {
            parent_entity_type: parent_action,
            child_entity_type: child_action,
        }
        duplicate_decision_summary = build_linked_duplicate_decision_summary(linked_actions, entity_type)

        if parent_action.get("mode") == "pending_decision" or child_action.get("mode") == "pending_decision":
            pending_decision_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "pending_decision",
                    "fields": build_linked_result_fields(linked_payload, entity_type=entity_type),
                    **duplicate_decision_summary,
                }
            )
            _report_dry_run_progress(
                progress_callback,
                checked_rows=checked_rows,
                ready_rows=ready_rows,
                skipped_rows=skipped_rows,
                pending_decision_rows=pending_decision_rows,
            )
            continue

        has_updates = parent_action.get("mode") == "update" or child_action.get("mode") == "update"

        ready_rows += 1
        if has_updates:
            ready_update_rows += 1
            result_item = {
                "row_number": row_number,
                "status": "ready_update",
                "fields": build_linked_result_fields(linked_payload, entity_type=entity_type),
            }
        else:
            ready_create_rows += 1
            result_item = {
                "row_number": row_number,
                "status": "ready",
                "fields": build_linked_result_fields(linked_payload, entity_type=entity_type),
            }

        if child_action.get("record_id") is not None:
            result_item["record_id"] = child_action["record_id"]

        if duplicate_decision_summary.get("linked"):
            result_item["linked"] = duplicate_decision_summary["linked"]
        results.append(result_item)
        _report_dry_run_progress(
            progress_callback,
            checked_rows=checked_rows,
            ready_rows=ready_rows,
            skipped_rows=skipped_rows,
            pending_decision_rows=pending_decision_rows,
        )

    return {
        "checked_rows": checked_rows,
        "ready_rows": ready_rows,
        "ready_create_rows": ready_create_rows,
        "ready_update_rows": ready_update_rows,
        "skipped_rows": skipped_rows,
        "pending_decision_rows": pending_decision_rows,
        "cancelled": was_cancelled,
        "cancelled_rows": cancelled_rows,
        "remaining_rows": cancelled_rows,
        "results": results,
    }


def execute_linked_import(
    *,
    account,
    entity_type: str = LINKED_COMPANY_CONTACT_ENTITY_TYPE,
    rows: list[list],
    row_numbers: list[int],
    columns: list[str],
    data_start_row: int,
    mapping: dict,
    validation_summary: dict,
    fields: list[dict],
    dedup_settings: dict,
    should_cancel=None,
    default_field_values: dict | None = None,
    per_row_decisions: dict | None = None,
    progress_callback=None,
    on_rate_limit_pause=None,
    on_rate_limit_resume=None,
) -> dict:
    invalid_row_numbers = get_invalid_row_numbers(validation_summary)
    user_resolver = BitrixUserResolver(account)
    checked_rows = 0
    created_rows = 0
    updated_rows = 0
    failed_rows = 0
    skipped_rows = 0
    cancelled_rows = 0
    created_ids = []
    updated_ids = []
    results = []
    was_cancelled = False
    parent_entity_type = get_linked_parent_entity_type(entity_type)
    child_entity_type = get_linked_child_entity_type(entity_type)
    relation_strategy = get_linked_relation_strategy(entity_type)
    relation_mode = str(relation_strategy.get("mode") or "").strip()
    relation_field = str(relation_strategy.get("field") or "").strip()
    child_link_field = relation_field if relation_mode == "field" else ""
    parent_link_field = relation_field if relation_mode == "parent_field" else ""
    parent_ext_key_cache: dict[str, int] = {}
    _parent_dedup_cache: dict = {}
    _child_dedup_lookup_cache: dict = {}
    _warm_dedup_cache(
        account=account,
        entity_type=child_entity_type,
        rows=rows,
        row_numbers=row_numbers,
        columns=columns,
        data_start_row=data_start_row,
        mapping=mapping,
        fields=fields,
        normalized_dedup_settings=normalize_dedup_settings(dedup_settings.get(child_entity_type, {})),
        cache=_child_dedup_lookup_cache,
        user_resolver=user_resolver,
        default_field_values=default_field_values,
    )

    current_row_delay = BITRIX_ROW_DELAY
    _row_state = {"had_retry": False}

    def _on_row_pause(wait_seconds):
        _row_state["had_retry"] = True
        if callable(on_rate_limit_pause):
            on_rate_limit_pause(wait_seconds)

    def _on_row_resume():
        if callable(on_rate_limit_resume):
            on_rate_limit_resume()

    for row_index, row_number in enumerate(row_numbers):
        if row_number < data_start_row:
            continue

        row = rows[row_index] if row_index < len(rows) else []
        if not row_has_values(row):
            continue

        if callable(should_cancel) and should_cancel():
            was_cancelled = True
            for remaining_index in range(row_index, len(row_numbers)):
                remaining_row_number = row_numbers[remaining_index]
                if remaining_row_number < data_start_row:
                    continue

                remaining_row = rows[remaining_index] if remaining_index < len(rows) else []
                if not row_has_values(remaining_row):
                    continue

                cancelled_rows += 1
                results.append(
                    {
                        "row_number": remaining_row_number,
                        "status": "cancelled",
                        "error": "Import was cancelled before row execution",
                        **build_import_result_report_meta(entity_type),
                    }
                )
            break

        checked_rows += 1
        _row_state["had_retry"] = False
        _sleep_if_configured(current_row_delay)
        _report_progress(
            progress_callback,
            checked_rows=checked_rows,
            created_rows=created_rows,
            updated_rows=updated_rows,
            failed_rows=failed_rows,
        )

        if row_number in invalid_row_numbers:
            skipped_rows += 1
            failed_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "skipped",
                    "error": "Row has validation issues",
                    **build_import_result_report_meta(entity_type),
                }
            )
            continue

        try:
            linked_payload = build_linked_row_payload(
                row,
                columns,
                mapping,
                fields,
                entity_type=entity_type,
                account=account,
                user_resolver=user_resolver,
                default_field_values=default_field_values,
            )
        except Exception as error:
            failed_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "failed",
                    "error": safe_format_import_error(error),
                    **build_import_result_report_meta(entity_type),
                }
            )
            continue

        parent_payload = dict(linked_payload.get(parent_entity_type, {}))
        ext_key = str(parent_payload.pop("EXTERNAL_KEY", "") or "").strip()
        if ext_key:
            parent_payload["XML_ID"] = ext_key
        child_payload = linked_payload.get(child_entity_type, {})
        _child_dedup_key = build_dedup_lookup_cache_key(
            child_entity_type,
            child_payload,
            filter_dedup_settings_for_payload(dedup_settings.get(child_entity_type, {}), child_payload),
        ) if child_payload else None
        decisions = per_row_decisions if isinstance(per_row_decisions, dict) else {}
        parent_row_decision = resolve_linked_row_decision(decisions, row_number, parent_entity_type)
        child_row_decision = resolve_linked_row_decision(decisions, row_number, child_entity_type)

        _parent_dedup_key = build_dedup_lookup_cache_key(
            parent_entity_type, parent_payload, dedup_settings.get(parent_entity_type, {}),
        ) if not ext_key and parent_payload else None

        try:
            if ext_key and ext_key in parent_ext_key_cache:
                parent_action = {"mode": "cached", "record_id": parent_ext_key_cache[ext_key], "meta": {}}
            elif _parent_dedup_key is not None and _parent_dedup_key in _parent_dedup_cache:
                parent_action = {"mode": "cached", "record_id": _parent_dedup_cache[_parent_dedup_key], "meta": {}}
            elif parent_payload:
                parent_action = _bitrix_retry(
                    lambda: resolve_linked_record_action_with_decision(
                        account, parent_entity_type, parent_payload, dedup_settings.get(parent_entity_type, {}),
                        parent_row_decision,
                    ),
                    on_pause=_on_row_pause, on_resume=_on_row_resume,
                )
            else:
                parent_action = {"mode": "skip_payload", "record_id": None, "meta": {}}
            child_action = _bitrix_retry(
                lambda: resolve_linked_record_action_with_decision(
                    account, child_entity_type, child_payload, dedup_settings.get(child_entity_type, {}),
                    child_row_decision,
                    find_existing_record_fn=lambda acc, et, rp, ds: find_existing_record_cached(
                        acc, et, rp, ds, cache=_child_dedup_lookup_cache,
                    ),
                ),
                on_pause=_on_row_pause, on_resume=_on_row_resume,
            ) if child_payload else {"mode": "skip_payload", "record_id": None, "meta": {}}
        except Exception as error:
            failed_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "failed",
                    "error": safe_format_import_error(error),
                    **build_import_result_report_meta(entity_type, linked_payload=linked_payload),
                }
            )
            continue

        linked_actions = {
            parent_entity_type: parent_action,
            child_entity_type: child_action,
        }
        duplicate_decision_summary = build_linked_duplicate_decision_summary(linked_actions, entity_type)

        if parent_action.get("mode") == "pending_decision" or child_action.get("mode") == "pending_decision":
            skipped_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "skipped_duplicate",
                    "error": "Duplicate skipped: no decision provided",
                    **duplicate_decision_summary,
                    **build_import_result_report_meta(entity_type, linked_payload=linked_payload),
                }
            )
            continue

        if parent_action.get("mode") == "skip_row" or child_action.get("mode") == "skip_row":
            skipped_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "skipped_duplicate",
                    "error": "Duplicate skipped by user decision",
                    **duplicate_decision_summary,
                    **build_import_result_report_meta(entity_type, linked_payload=linked_payload),
                }
            )
            continue

        parent_record_id = parent_action.get("record_id")
        try:
            if parent_payload and parent_action["mode"] != "cached":
                if parent_action["mode"] == "update":
                    _bitrix_retry(
                        lambda: update_entity_record(account, parent_entity_type, parent_action["record_id"], parent_payload),
                        on_pause=_on_row_pause, on_resume=_on_row_resume,
                    )
                elif parent_action["mode"] == "create":
                    parent_record_id = _bitrix_retry(
                        lambda: create_entity_record(account, parent_entity_type, parent_payload),
                        on_pause=_on_row_pause, on_resume=_on_row_resume,
                    )
            if ext_key and parent_record_id is not None:
                parent_ext_key_cache[ext_key] = parent_record_id
            if _parent_dedup_key is not None and parent_record_id is not None:
                _parent_dedup_cache[_parent_dedup_key] = parent_record_id
        except Exception as error:
            failed_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "failed",
                    "error": safe_format_import_error(error),
                    **build_import_result_report_meta(entity_type, linked_payload=linked_payload),
                }
            )
            continue

        if child_link_field and parent_record_id is not None and child_payload:
            child_payload = {
                **child_payload,
                child_link_field: normalize_record_id(parent_record_id) or parent_record_id,
            }

        child_record_id = child_action.get("record_id")
        try:
            if child_payload:
                if child_action["mode"] == "update":
                    _bitrix_retry(
                        lambda: update_entity_record(account, child_entity_type, child_action["record_id"], child_payload),
                        on_pause=_on_row_pause, on_resume=_on_row_resume,
                    )
                elif child_link_field and child_action["mode"] == "reuse" and parent_record_id is not None and child_action["record_id"] is not None:
                    _bitrix_retry(
                        lambda: update_entity_record(account, child_entity_type, child_action["record_id"], {child_link_field: parent_record_id}),
                        on_pause=_on_row_pause, on_resume=_on_row_resume,
                    )
                elif child_action["mode"] == "create":
                    child_record_id = _bitrix_retry(
                        lambda: create_entity_record(account, child_entity_type, child_payload),
                        on_pause=_on_row_pause, on_resume=_on_row_resume,
                    )
                    if _child_dedup_key is not None and child_record_id is not None:
                        _child_dedup_lookup_cache[_child_dedup_key] = {
                            "record_id": child_record_id,
                            "duplicate_match_fields": [],
                            "dedup_missing_fields": [],
                        }

            if relation_mode == "parent_field" and parent_record_id is not None and child_record_id is not None and parent_link_field:
                _bitrix_retry(
                    lambda: update_entity_record(
                        account,
                        parent_entity_type,
                        parent_record_id,
                        {parent_link_field: normalize_record_id(child_record_id) or child_record_id},
                    ),
                    on_pause=_on_row_pause, on_resume=_on_row_resume,
                )
            if relation_mode == "deal_contact_binding" and parent_record_id is not None and child_record_id is not None:
                _bitrix_retry(
                    lambda: bind_deal_contact(account, deal_id=parent_record_id, contact_id=child_record_id),
                    on_pause=_on_row_pause, on_resume=_on_row_resume,
                )
            if relation_mode == "contact_company_binding" and parent_record_id is not None and child_record_id is not None:
                _bitrix_retry(
                    lambda: bind_contact_company(account, contact_id=parent_record_id, company_id=child_record_id),
                    on_pause=_on_row_pause, on_resume=_on_row_resume,
                )
        except Exception as error:
            failed_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "failed",
                    "error": safe_format_import_error(error),
                    **build_import_result_report_meta(entity_type, linked_payload=linked_payload),
                }
            )
            continue

        if _row_state["had_retry"]:
            current_row_delay = min(current_row_delay * 2, 5.0)
            logging.info(
                "Linked import: rate limit recovered; increasing row delay to %.1fs for entity_type=%s",
                current_row_delay, entity_type,
            )

        has_child_link_update = (
            child_action.get("mode") == "reuse"
            and bool(child_link_field)
            and parent_record_id is not None
            and child_action.get("record_id") is not None
        )
        has_parent_link_update = (
            relation_mode == "parent_field"
            and child_action.get("mode") == "reuse"
            and parent_record_id is not None
            and child_action.get("record_id") is not None
        )
        has_relation_binding_update = (
            relation_mode in {"deal_contact_binding", "contact_company_binding"}
            and child_action.get("mode") == "reuse"
            and parent_record_id is not None
            and child_action.get("record_id") is not None
        )
        has_updates = (
            parent_action.get("mode") == "update"
            or child_action.get("mode") == "update"
            or has_parent_link_update
            or has_child_link_update
            or has_relation_binding_update
        )
        linked_records = {}
        linked_entity_payloads = {
            parent_entity_type: parent_payload,
            child_entity_type: child_payload,
        }
        linked_entity_record_ids = {
            parent_entity_type: parent_record_id,
            child_entity_type: child_record_id,
        }
        for linked_entity in get_linked_entity_ids(entity_type):
            linked_record = build_linked_record_result(
                linked_entity,
                linked_entity_payloads.get(linked_entity, {}),
                linked_entity_record_ids.get(linked_entity),
                linked_actions.get(linked_entity, {}).get("mode", ""),
            )
            if linked_record is not None:
                linked_records[linked_entity] = linked_record
        result_item = {
            "row_number": row_number,
            "status": "updated" if has_updates else "created",
            **build_import_result_report_meta(
                entity_type,
                record_id=child_record_id,
                linked_records=linked_records,
                linked_payload=linked_payload,
            ),
        }
        if duplicate_decision_summary.get("linked"):
            result_item["linked"] = duplicate_decision_summary["linked"]
        if linked_records:
            result_item["linked_records"] = linked_records
        if child_record_id is not None:
            result_item["record_id"] = child_record_id

        if has_updates:
            updated_rows += 1
            if child_record_id is not None:
                updated_ids.append(child_record_id)
        else:
            created_rows += 1
            if child_record_id is not None:
                created_ids.append(child_record_id)

        results.append(result_item)

    return {
        "checked_rows": checked_rows,
        "created_rows": created_rows,
        "updated_rows": updated_rows,
        "failed_rows": failed_rows,
        "skipped_rows": skipped_rows,
        "cancelled": was_cancelled,
        "cancelled_rows": cancelled_rows,
        "remaining_rows": cancelled_rows,
        "created_ids": created_ids,
        "updated_ids": updated_ids,
        "results": results,
    }


def execute_dry_run(
    *,
    account,
    entity_type: str,
    rows: list[list],
    row_numbers: list[int],
    columns: list[str],
    data_start_row: int,
    mapping: dict,
    validation_summary: dict,
    fields: list[dict],
    dedup_settings=None,
    should_cancel=None,
    default_field_values: dict | None = None,
    progress_callback=None,
    warm_progress_callback=None,
    entity_config: dict | None = None,
) -> dict:
    if is_linked_import_entity_type(entity_type):
        return execute_linked_dry_run(
            account=account,
            entity_type=entity_type,
            rows=rows,
            row_numbers=row_numbers,
            columns=columns,
            data_start_row=data_start_row,
            mapping=mapping,
            validation_summary=validation_summary,
            fields=fields,
            dedup_settings=normalize_linked_dedup_settings(dedup_settings, entity_type=entity_type),
            should_cancel=should_cancel,
            default_field_values=default_field_values,
            progress_callback=progress_callback,
            warm_progress_callback=warm_progress_callback,
        )

    invalid_row_numbers = get_invalid_row_numbers(validation_summary)
    normalized_dedup_settings = normalize_dedup_settings(dedup_settings)
    user_resolver = BitrixUserResolver(account)
    dry_run_context = {"entity_config": dict(entity_config)} if entity_type == SMART_PROCESS_ENTITY_TYPE and isinstance(entity_config, dict) else None
    dedup_lookup_cache: dict[tuple, dict | None] = {}
    _warm_dedup_cache(
        account=account,
        entity_type=entity_type,
        rows=rows,
        row_numbers=row_numbers,
        columns=columns,
        data_start_row=data_start_row,
        mapping=mapping,
        fields=fields,
        normalized_dedup_settings=normalized_dedup_settings,
        cache=dedup_lookup_cache,
        user_resolver=user_resolver,
        default_field_values=default_field_values,
        context=dry_run_context,
        warm_progress_callback=warm_progress_callback,
    )
    checked_rows = 0
    ready_rows = 0
    ready_create_rows = 0
    ready_update_rows = 0
    skipped_rows = 0
    pending_decision_rows = 0
    cancelled_rows = 0
    results = []
    was_cancelled = False

    for row_index, row_number in enumerate(row_numbers):
        if row_number < data_start_row:
            continue

        row = rows[row_index] if row_index < len(rows) else []
        if not row_has_values(row):
            continue

        if callable(should_cancel) and should_cancel():
            was_cancelled = True
            for remaining_index in range(row_index, len(row_numbers)):
                remaining_row_number = row_numbers[remaining_index]
                if remaining_row_number < data_start_row:
                    continue

                remaining_row = rows[remaining_index] if remaining_index < len(rows) else []
                if not row_has_values(remaining_row):
                    continue

                cancelled_rows += 1
                results.append(
                    {
                        "row_number": remaining_row_number,
                        "status": "cancelled",
                        "error": "Dry run was cancelled before row execution",
                    }
                )
            break

        checked_rows += 1

        if row_number in invalid_row_numbers:
            skipped_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "skipped",
                    "error": "Row has validation issues",
                }
            )
            _report_dry_run_progress(
                progress_callback,
                checked_rows=checked_rows,
                ready_rows=ready_rows,
                skipped_rows=skipped_rows,
                pending_decision_rows=pending_decision_rows,
            )
            continue

        # Sleep only when dedup lookups will actually hit Bitrix24.
        # For "create" strategy there are no API calls in dry run, so sleeping
        # would add BITRIX_ROW_DELAY × N_rows of dead time for nothing.
        _dedup_needs_api = (
            normalized_dedup_settings["strategy"] != "create"
            and bool(normalized_dedup_settings.get("fields"))
        )
        if _dedup_needs_api:
            _sleep_if_configured(BITRIX_ROW_DELAY)
        row_payload = build_row_payload(
            row,
            columns,
            mapping,
            fields,
            account=account,
            user_resolver=user_resolver,
            default_field_values=default_field_values,
        )
        existing_record_match = _bitrix_retry(
            lambda: find_existing_record_cached(
                account,
                entity_type,
                row_payload,
                normalized_dedup_settings,
                cache=dedup_lookup_cache,
                context=dry_run_context,
            )
        )
        existing_record_id = existing_record_match.get("record_id") if isinstance(existing_record_match, dict) else None
        duplicate_match_fields = existing_record_match.get("duplicate_match_fields", []) if isinstance(existing_record_match, dict) else []
        dedup_missing_fields = existing_record_match.get("dedup_missing_fields", []) if isinstance(existing_record_match, dict) else []
        dedup_result_meta = {}
        if duplicate_match_fields:
            dedup_result_meta["duplicate_match_fields"] = duplicate_match_fields
        if dedup_missing_fields:
            dedup_result_meta["dedup_missing_fields"] = dedup_missing_fields

        if existing_record_id is not None and normalized_dedup_settings["strategy"] == "skip":
            skipped_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "skipped_duplicate",
                    "record_id": existing_record_id,
                    **dedup_result_meta,
                    "error": "Duplicate matched existing record",
                }
            )
            _report_dry_run_progress(
                progress_callback,
                checked_rows=checked_rows,
                ready_rows=ready_rows,
                skipped_rows=skipped_rows,
                pending_decision_rows=pending_decision_rows,
            )
            continue

        if existing_record_id is not None and normalized_dedup_settings["strategy"] == "ask":
            pending_decision_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "pending_decision",
                    "record_id": existing_record_id,
                    **dedup_result_meta,
                    "fields": row_payload,
                }
            )
            _report_dry_run_progress(
                progress_callback,
                checked_rows=checked_rows,
                ready_rows=ready_rows,
                skipped_rows=skipped_rows,
                pending_decision_rows=pending_decision_rows,
            )
            continue

        ready_rows += 1
        if existing_record_id is not None and normalized_dedup_settings["strategy"] == "update":
            ready_update_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "ready_update",
                    "record_id": existing_record_id,
                    **dedup_result_meta,
                    "fields": row_payload,
                }
            )
            _report_dry_run_progress(
                progress_callback,
                checked_rows=checked_rows,
                ready_rows=ready_rows,
                skipped_rows=skipped_rows,
                pending_decision_rows=pending_decision_rows,
            )
            continue

        ready_create_rows += 1
        results.append(
            {
                "row_number": row_number,
                "status": "ready",
                **dedup_result_meta,
                "fields": row_payload,
            }
        )
        _report_dry_run_progress(
            progress_callback,
            checked_rows=checked_rows,
            ready_rows=ready_rows,
            skipped_rows=skipped_rows,
            pending_decision_rows=pending_decision_rows,
        )

    return {
        "checked_rows": checked_rows,
        "ready_rows": ready_rows,
        "ready_create_rows": ready_create_rows,
        "ready_update_rows": ready_update_rows,
        "skipped_rows": skipped_rows,
        "pending_decision_rows": pending_decision_rows,
        "cancelled": was_cancelled,
        "cancelled_rows": cancelled_rows,
        "remaining_rows": cancelled_rows,
        "results": results,
    }


def execute_import(
    *,
    account,
    entity_type: str,
    rows: list[list],
    row_numbers: list[int],
    columns: list[str],
    data_start_row: int,
    mapping: dict,
    validation_summary: dict,
    fields: list[dict],
    dedup_settings=None,
    should_cancel=None,
    default_field_values: dict | None = None,
    per_row_decisions: dict | None = None,
    progress_callback=None,
    warm_progress_callback=None,
    entity_config: dict | None = None,
    on_rate_limit_pause=None,
    on_rate_limit_resume=None,
) -> dict:
    if is_linked_import_entity_type(entity_type):
        return execute_linked_import(
            account=account,
            entity_type=entity_type,
            rows=rows,
            row_numbers=row_numbers,
            columns=columns,
            data_start_row=data_start_row,
            mapping=mapping,
            validation_summary=validation_summary,
            fields=fields,
            dedup_settings=normalize_linked_dedup_settings(dedup_settings, entity_type=entity_type),
            should_cancel=should_cancel,
            default_field_values=default_field_values,
            per_row_decisions=per_row_decisions,
            progress_callback=progress_callback,
            on_rate_limit_pause=on_rate_limit_pause,
            on_rate_limit_resume=on_rate_limit_resume,
        )

    invalid_row_numbers = get_invalid_row_numbers(validation_summary)
    normalized_dedup_settings = normalize_dedup_settings(dedup_settings)
    user_resolver = BitrixUserResolver(account)
    import_context = {}
    if entity_type == "task_checklist_item":
        import_context["checklist_group_cache"] = {}
    if entity_type == SMART_PROCESS_ENTITY_TYPE and isinstance(entity_config, dict):
        import_context["entity_config"] = dict(entity_config)
    if not import_context:
        import_context = None
    import_dedup_cache: dict[tuple, dict | None] = {}
    _warm_dedup_cache(
        account=account,
        entity_type=entity_type,
        rows=rows,
        row_numbers=row_numbers,
        columns=columns,
        data_start_row=data_start_row,
        mapping=mapping,
        fields=fields,
        normalized_dedup_settings=normalized_dedup_settings,
        cache=import_dedup_cache,
        user_resolver=user_resolver,
        default_field_values=default_field_values,
        context=import_context,
        warm_progress_callback=warm_progress_callback,
    )
    checked_rows = 0
    created_rows = 0
    updated_rows = 0
    failed_rows = 0
    skipped_rows = 0
    cancelled_rows = 0
    created_ids = []
    updated_ids = []
    results = []
    was_cancelled = False
    oauth_abort_error: str = ""
    fatal_error: str = ""
    use_batch = _is_batch_eligible(entity_type, normalized_dedup_settings)
    pending_batch: list = []
    current_batch_size = _get_batch_size(entity_type)
    current_row_delay = BITRIX_ROW_DELAY
    report_entity_config = (import_context or {}).get("entity_config") if isinstance(import_context, dict) else None

    _nb_row_state = {"had_retry": False}

    def _on_nb_row_pause(wait_seconds):
        _nb_row_state["had_retry"] = True
        if callable(on_rate_limit_pause):
            on_rate_limit_pause(wait_seconds)

    def _on_nb_row_resume():
        if callable(on_rate_limit_resume):
            on_rate_limit_resume()

    def _update_existing_record(record_id, row_payload: dict):
        if entity_type == SMART_PROCESS_ENTITY_TYPE:
            return update_smart_process_record(account, report_entity_config or {}, record_id, row_payload)
        return update_entity_record(account, entity_type, record_id, row_payload)

    def _flush_pending_batch():
        nonlocal created_rows, failed_rows, current_batch_size
        if not pending_batch:
            return
        _sleep_if_configured(BITRIX_BATCH_DELAY)

        had_retry = False

        def _on_batch_pause(wait_seconds):
            nonlocal had_retry
            had_retry = True
            if callable(on_rate_limit_pause):
                on_rate_limit_pause(wait_seconds)

        def _on_batch_resume():
            if callable(on_rate_limit_resume):
                on_rate_limit_resume()

        try:
            batch_results, batch_created, batch_failed, batch_ids = _flush_crm_batch_with_fallback(
                account,
                entity_type,
                list(pending_batch),
                on_pause=_on_batch_pause,
                on_resume=_on_batch_resume,
            )
        except Exception as error:
            if _is_rate_limit_error(error) or _is_operation_time_limit_error(error):
                current_batch_size = max(_BATCH_SIZE_MIN, current_batch_size // 2)
                logging.warning(
                    "Batch failed with limit error; reducing batch size to %d for entity_type=%s",
                    current_batch_size,
                    entity_type,
                )
            for prow_number, pending_row_payload in pending_batch:
                failed_rows += 1
                results.append(
                    {
                        "row_number": prow_number,
                        "status": "failed",
                        "error": safe_format_import_error(error),
                        **build_import_result_report_meta(
                            entity_type,
                            row_payload=pending_row_payload,
                            entity_config=report_entity_config,
                        ),
                    }
                )
            pending_batch.clear()
            return

        if had_retry:
            current_batch_size = max(_BATCH_SIZE_MIN, current_batch_size // 2)
            _sleep_if_configured(BITRIX_BATCH_DELAY)
            logging.info(
                "Batch recovered after retry; reducing batch size to %d for entity_type=%s",
                current_batch_size,
                entity_type,
            )

        results.extend(batch_results)
        created_rows += batch_created
        failed_rows += batch_failed
        created_ids.extend(batch_ids)
        pending_batch.clear()

    for row_index, row_number in enumerate(row_numbers):
        if row_number < data_start_row:
            continue

        row = rows[row_index] if row_index < len(rows) else []
        if not row_has_values(row):
            continue

        if callable(should_cancel) and should_cancel():
            was_cancelled = True
            _flush_pending_batch()
            for remaining_index in range(row_index, len(row_numbers)):
                remaining_row_number = row_numbers[remaining_index]
                if remaining_row_number < data_start_row:
                    continue

                remaining_row = rows[remaining_index] if remaining_index < len(rows) else []
                if not row_has_values(remaining_row):
                    continue

                cancelled_rows += 1
                results.append(
                    {
                        "row_number": remaining_row_number,
                        "status": "cancelled",
                        "error": "Import was cancelled before row execution",
                        **build_import_result_report_meta(entity_type, entity_config=report_entity_config),
                    }
                )
            break

        checked_rows += 1
        if not use_batch:
            if _nb_row_state["had_retry"]:
                current_row_delay = min(current_row_delay * 2, 5.0)
                logging.info(
                    "Non-batch: rate limit recovered; increasing row delay to %.1fs for entity_type=%s",
                    current_row_delay, entity_type,
                )
            _nb_row_state["had_retry"] = False
            _sleep_if_configured(current_row_delay)

        _report_progress(
            progress_callback,
            checked_rows=checked_rows,
            created_rows=created_rows,
            updated_rows=updated_rows,
            failed_rows=failed_rows,
        )

        if row_number in invalid_row_numbers:
            skipped_rows += 1
            failed_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "skipped",
                    "error": "Row has validation issues",
                    **build_import_result_report_meta(entity_type, entity_config=report_entity_config),
                }
            )
            continue

        try:
            row_payload = build_row_payload(
                row,
                columns,
                mapping,
                fields,
                account=account,
                user_resolver=user_resolver,
                default_field_values=default_field_values,
            )
        except Exception as error:
            if isinstance(error, BitrixOAuthInvalidGrant):
                oauth_abort_error = safe_format_import_error(error)
            elif not fatal_error:
                fatal_error = _resolve_fatal_import_error(error, entity_type=entity_type)
            formatted_error = fatal_error or safe_format_import_error(error)
            failed_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "failed",
                    "error": formatted_error,
                    **build_import_result_report_meta(entity_type, entity_config=report_entity_config),
                }
            )
            if oauth_abort_error or fatal_error:
                break
            continue

        _row_uf_file_fields: dict = {}
        if entity_type in _UF_FILE_ENTITY_TYPES:
            _row_uf_file_fields, row_payload = _extract_uf_file_fields(row_payload, fields)

        if use_batch and not _row_uf_file_fields:
            pending_batch.append((row_number, row_payload))
            if len(pending_batch) >= current_batch_size:
                _flush_pending_batch()
                if callable(progress_callback):
                    progress_callback(
                        checked_rows=checked_rows,
                        created_rows=created_rows,
                        updated_rows=updated_rows,
                        failed_rows=failed_rows,
                    )
            continue

        try:
            existing_record_match = _bitrix_retry(
                lambda rp=row_payload: find_existing_record_cached(
                    account,
                    entity_type,
                    rp,
                    normalized_dedup_settings,
                    cache=import_dedup_cache,
                    context=import_context,
                ),
                on_pause=_on_nb_row_pause, on_resume=_on_nb_row_resume,
            )
        except Exception as error:
            if isinstance(error, BitrixOAuthInvalidGrant):
                oauth_abort_error = safe_format_import_error(error)
            elif not fatal_error:
                fatal_error = _resolve_fatal_import_error(error, entity_type=entity_type)
            formatted_error = fatal_error or safe_format_import_error(error)
            failed_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "failed",
                    "error": formatted_error,
                    **build_import_result_report_meta(
                        entity_type,
                        row_payload=row_payload,
                        entity_config=report_entity_config,
                    ),
                }
            )
            if oauth_abort_error or fatal_error:
                break
            continue

        existing_record_id = existing_record_match.get("record_id") if isinstance(existing_record_match, dict) else None
        duplicate_match_fields = existing_record_match.get("duplicate_match_fields", []) if isinstance(existing_record_match, dict) else []
        dedup_missing_fields = existing_record_match.get("dedup_missing_fields", []) if isinstance(existing_record_match, dict) else []
        dedup_result_meta = {}
        if duplicate_match_fields:
            dedup_result_meta["duplicate_match_fields"] = duplicate_match_fields
        if dedup_missing_fields:
            dedup_result_meta["dedup_missing_fields"] = dedup_missing_fields

        if existing_record_id is not None and normalized_dedup_settings["strategy"] == "skip":
            skipped_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "skipped_duplicate",
                    "record_id": existing_record_id,
                    **dedup_result_meta,
                    "error": "Duplicate matched existing record",
                    **build_import_result_report_meta(
                        entity_type,
                        row_payload=row_payload,
                        record_id=existing_record_id,
                        entity_config=report_entity_config,
                    ),
                }
            )
            continue

        if existing_record_id is not None and normalized_dedup_settings["strategy"] == "ask":
            decisions = per_row_decisions if isinstance(per_row_decisions, dict) else {}
            row_decision = str(decisions.get(str(row_number), "skip")).strip().lower()
            if row_decision not in {"create", "update", "skip"}:
                row_decision = "skip"

            if row_decision == "skip":
                skipped_rows += 1
                results.append(
                    {
                        "row_number": row_number,
                        "status": "skipped_duplicate",
                        "record_id": existing_record_id,
                        **dedup_result_meta,
                        "error": "Duplicate skipped by user decision",
                        **build_import_result_report_meta(
                            entity_type,
                            row_payload=row_payload,
                            record_id=existing_record_id,
                            entity_config=report_entity_config,
                        ),
                    }
                )
                continue
            elif row_decision == "update":
                try:
                    _bitrix_retry(
                        lambda: _update_existing_record(existing_record_id, row_payload),
                        on_pause=_on_nb_row_pause, on_resume=_on_nb_row_resume,
                    )
                except Exception as error:
                    if isinstance(error, BitrixOAuthInvalidGrant):
                        oauth_abort_error = safe_format_import_error(error)
                    elif not fatal_error:
                        fatal_error = _resolve_fatal_import_error(error, entity_type=entity_type)
                    formatted_error = fatal_error or safe_format_import_error(error)
                    failed_rows += 1
                    results.append(
                        {
                            "row_number": row_number,
                            "status": "failed",
                            "error": formatted_error,
                            **build_import_result_report_meta(
                                entity_type,
                                row_payload=row_payload,
                                record_id=existing_record_id,
                                entity_config=report_entity_config,
                            ),
                        }
                    )
                    if oauth_abort_error or fatal_error:
                        break
                    continue
                updated_rows += 1
                updated_ids.append(existing_record_id)
                results.append(
                    {
                        "row_number": row_number,
                        "status": "updated",
                        "record_id": existing_record_id,
                        "updated_fields": list(row_payload.keys()),
                        **dedup_result_meta,
                        **build_import_result_report_meta(
                            entity_type,
                            row_payload=row_payload,
                            record_id=existing_record_id,
                            entity_config=report_entity_config,
                        ),
                    }
                )
                if _row_uf_file_fields:
                    _file_errors = _attach_uf_file_fields(account, entity_type, existing_record_id, _row_uf_file_fields, context=import_context)
                    if _file_errors:
                        results[-1]["file_attachment_error"] = "; ".join(_file_errors)
                continue
            # row_decision == "create" → falls through to create logic below

        if existing_record_id is not None and normalized_dedup_settings["strategy"] == "update":
            try:
                _bitrix_retry(
                    lambda: _update_existing_record(existing_record_id, row_payload),
                    on_pause=_on_nb_row_pause, on_resume=_on_nb_row_resume,
                )
            except Exception as error:
                if isinstance(error, BitrixOAuthInvalidGrant):
                    oauth_abort_error = safe_format_import_error(error)
                elif not fatal_error:
                    fatal_error = _resolve_fatal_import_error(error, entity_type=entity_type)
                formatted_error = fatal_error or safe_format_import_error(error)
                failed_rows += 1
                results.append(
                    {
                        "row_number": row_number,
                        "status": "failed",
                        "error": formatted_error,
                        **build_import_result_report_meta(
                            entity_type,
                            row_payload=row_payload,
                            record_id=existing_record_id,
                            entity_config=report_entity_config,
                        ),
                    }
                )
                if oauth_abort_error or fatal_error:
                    break
                continue

            updated_rows += 1
            updated_ids.append(existing_record_id)
            results.append(
                {
                    "row_number": row_number,
                    "status": "updated",
                    "record_id": existing_record_id,
                    "updated_fields": list(row_payload.keys()),
                    **dedup_result_meta,
                    **build_import_result_report_meta(
                        entity_type,
                        row_payload=row_payload,
                        record_id=existing_record_id,
                        entity_config=report_entity_config,
                    ),
                }
            )
            if _row_uf_file_fields:
                _file_errors = _attach_uf_file_fields(account, entity_type, existing_record_id, _row_uf_file_fields, context=import_context)
                if _file_errors:
                    results[-1]["file_attachment_error"] = "; ".join(_file_errors)
            continue

        try:
            record_id = _bitrix_retry(
                lambda: create_entity_record(account, entity_type, row_payload, context=import_context),
                on_pause=_on_nb_row_pause,
                on_resume=_on_nb_row_resume,
                allow_unknown_error_as_operation_time_limit=entity_type != "user",
            )
        except Exception as error:
            if isinstance(error, BitrixOAuthInvalidGrant):
                oauth_abort_error = safe_format_import_error(error)
            elif not fatal_error:
                fatal_error = _resolve_fatal_import_error(error, entity_type=entity_type)
            formatted_error = fatal_error or safe_format_import_error(error)
            failed_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "failed",
                    "error": formatted_error,
                    **build_import_result_report_meta(
                        entity_type,
                        row_payload=row_payload,
                        entity_config=report_entity_config,
                    ),
                }
            )
            if oauth_abort_error or fatal_error:
                break
            continue

        created_rows += 1
        result_item = {
            "row_number": row_number,
            "status": "created",
            **dedup_result_meta,
            **build_import_result_report_meta(
                entity_type,
                row_payload=row_payload,
                record_id=record_id,
                entity_config=report_entity_config,
            ),
        }
        if record_id is not None:
            created_ids.append(record_id)
            result_item["record_id"] = record_id
        results.append(result_item)
        if record_id is not None and _row_uf_file_fields:
            _file_errors = _attach_uf_file_fields(account, entity_type, record_id, _row_uf_file_fields, context=import_context)
            if _file_errors:
                results[-1]["file_attachment_error"] = "; ".join(_file_errors)

    terminal_abort_error = str(oauth_abort_error or fatal_error or "").strip()
    if terminal_abort_error:
        processed_row_numbers = {r["row_number"] for r in results}
        for rem_idx, rem_num in enumerate(row_numbers):
            if rem_num < data_start_row or rem_num in processed_row_numbers:
                continue
            rem_row = rows[rem_idx] if rem_idx < len(rows) else []
            if not row_has_values(rem_row):
                continue
            cancelled_rows += 1
            was_cancelled = True
            results.append({
                "row_number": rem_num,
                "status": "cancelled",
                "error": terminal_abort_error,
            })
    else:
        _flush_pending_batch()

    return {
        "checked_rows": checked_rows,
        "created_rows": created_rows,
        "updated_rows": updated_rows,
        "failed_rows": failed_rows,
        "skipped_rows": skipped_rows,
        "cancelled": was_cancelled,
        "cancelled_rows": cancelled_rows,
        "remaining_rows": cancelled_rows,
        "created_ids": created_ids,
        "updated_ids": updated_ids,
        "results": results,
        "auth_error": oauth_abort_error,
        "fatal_error": fatal_error,
    }
