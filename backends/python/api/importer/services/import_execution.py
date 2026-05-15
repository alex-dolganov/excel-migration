import re
import time

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
from .task_attachments import attach_file_to_crm_entity, attach_file_to_task, download_attachment_source
from .error_messages import MISSING_BITRIX_RECORD_ID_ERROR, safe_format_import_error
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
CRM_ACTIVITY_ENTITY_TYPES = {"crm_activity", "crm_note"}
CRM_ACTIVITY_COMMUNICATION_TYPES = {
    "2": "PHONE",
    "4": "EMAIL",
}
HR_ENTITY_TYPES = {"user", "department"}
LINKED_COMPANY_CONTACT_ENTITY_TYPE = "linked_company_contact"
LINKED_COMPANY_DEAL_ENTITY_TYPE = "linked_company_deal"
LINKED_COMPANY_CHILD_ENTITY_TYPES = {
    LINKED_COMPANY_CONTACT_ENTITY_TYPE: "contact",
    LINKED_COMPANY_DEAL_ENTITY_TYPE: "deal",
}

SUPPORTED_DEDUP_STRATEGIES = {"create", "skip", "update", "ask"}
SUPPORTED_DEDUP_FIELDS = {"EMAIL", "PHONE", "TITLE"}   # legacy whitelist kept for reference
_DEDUP_FIELD_RE = re.compile(r'^[A-Z][A-Z0-9_]*$')    # any valid Bitrix24 field name
BITRIX_MULTIFIELD_IDS = {"PHONE", "EMAIL", "WEB", "IM"}
TASK_CHILD_ENTITY_TYPES = {"task_comment", "task_checklist_item"}

BITRIX_ROW_DELAY = 0.5
BITRIX_BATCH_DELAY = 0.5
BATCH_SIZE = 50
PROGRESS_SAVE_INTERVAL = 10
_RATE_LIMIT_KEYWORDS = frozenset(["query_limit_exceeded", "too many requests", "rate limit", "overloaded", "429"])
_RATE_LIMIT_RETRY_WAITS = [5, 15, 30]

_CRM_BATCH_CREATE_METHODS = {
    "lead": "crm.lead.add",
    "contact": "crm.contact.add",
    "company": "crm.company.add",
    "deal": "crm.deal.add",
}


def _is_batch_eligible(entity_type: str, dedup_settings: dict) -> bool:
    return entity_type in _CRM_BATCH_CREATE_METHODS and dedup_settings.get("strategy") == "create"


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
                        "error": MISSING_BITRIX_RECORD_ID_ERROR,
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
    return any(kw in str(error).lower() for kw in _RATE_LIMIT_KEYWORDS)


def _bitrix_retry(fn):
    for attempt, wait in enumerate([0] + _RATE_LIMIT_RETRY_WAITS):
        if wait:
            time.sleep(wait)
        try:
            return fn()
        except Exception as error:
            if attempt >= len(_RATE_LIMIT_RETRY_WAITS) or not _is_rate_limit_error(error):
                raise


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


def get_linked_company_child_entity_type(entity_type: str) -> str:
    child_entity_type = LINKED_COMPANY_CHILD_ENTITY_TYPES.get(str(entity_type or "").strip())
    if not child_entity_type:
        raise ValueError(f"Unsupported linked import entity type: {entity_type}")
    return child_entity_type


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

    if field_type in {"boolean", "bool"}:
        return parse_boolean_value(normalized_value)

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
        normalized_field_name = str(field_name or "").strip().upper()
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
    if str(entity_type or "").strip() == SMART_PROCESS_ENTITY_TYPE:
        return normalize_dedup_settings({})
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
    response = BitrixAPIRequest(
        bitrix_token=account,
        api_method="user.add",
        params=fields,
    )
    result = unwrap_bitrix_result(response)
    if isinstance(result, dict):
        return normalize_record_id(result.get("ID") or result.get("id") or result.get("result"))
    return normalize_record_id(result)


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
        scope = _resolve_task_child_scope(client, "checklistitem")
        if scope is None:
            raise ValueError("Unsupported entity type")
        return scope

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


def build_dedup_lookup_filter(row_payload: dict, dedup_settings: dict) -> tuple[dict, list[str], list[str]]:
    lookup_filter = {}
    matched_fields = []
    missing_fields = []

    for field_name in dedup_settings["fields"]:
        field_value = extract_dedup_lookup_value(row_payload.get(field_name))
        if not field_value:
            missing_fields.append(field_name)
            continue
        lookup_filter[field_name] = field_value
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


def find_existing_record(account, entity_type: str, row_payload: dict, dedup_settings: dict):
    if dedup_settings["strategy"] == "create" or not dedup_settings["fields"]:
        return None

    if entity_type in TASK_ENTITY_TYPES or entity_type in CRM_FILES_ENTITY_TYPES or entity_type in CRM_ACTIVITY_ENTITY_TYPES:
        return None

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
) -> dict:
    filtered_dedup_settings = filter_dedup_settings_for_payload(dedup_settings, row_payload)
    existing_record_match = find_existing_record(account, entity_type, row_payload, filtered_dedup_settings)
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
        if isinstance(meta, dict) and meta:
            linked_meta[linked_entity] = meta

        record_id = normalize_record_id(linked_action.get("record_id")) or linked_action.get("record_id")
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


def update_entity_record(account, entity_type: str, record_id, fields: dict):
    if entity_type in TASK_ENTITY_TYPES or entity_type in CRM_FILES_ENTITY_TYPES or entity_type in CRM_ACTIVITY_ENTITY_TYPES:
        raise ValueError("Update is not supported for this entity type")

    if entity_type == "user":
        _update_user(account, record_id, fields)
        return True

    if entity_type == "department":
        _update_department(account, record_id, fields)
        return True

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
        task_scope = get_entity_scope(account.client, "task")
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
    default_field_values: dict | None = None,
) -> dict:
    invalid_row_numbers = get_invalid_row_numbers(validation_summary)
    user_resolver = BitrixUserResolver(account)
    checked_rows = 0
    ready_rows = 0
    ready_create_rows = 0
    ready_update_rows = 0
    skipped_rows = 0
    pending_decision_rows = 0
    results = []
    child_entity_type = get_linked_company_child_entity_type(entity_type)

    for row_index, row_number in enumerate(row_numbers):
        if row_number < data_start_row:
            continue

        row = rows[row_index] if row_index < len(rows) else []
        if not row_has_values(row):
            continue

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

        company_action = resolve_linked_record_action_with_decision(
            account,
            "company",
            linked_payload.get("company", {}),
            dedup_settings.get("company", {}),
            "",
        ) if linked_payload.get("company") else {"mode": "skip_payload", "record_id": None, "meta": {}}

        child_action = resolve_linked_record_action_with_decision(
            account,
            child_entity_type,
            linked_payload.get(child_entity_type, {}),
            dedup_settings.get(child_entity_type, {}),
            "",
        ) if linked_payload.get(child_entity_type) else {"mode": "skip_payload", "record_id": None, "meta": {}}

        linked_actions = {
            "company": company_action,
            child_entity_type: child_action,
        }
        duplicate_decision_summary = build_linked_duplicate_decision_summary(linked_actions, entity_type)

        if company_action.get("mode") == "pending_decision" or child_action.get("mode") == "pending_decision":
            pending_decision_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "pending_decision",
                    "fields": build_linked_result_fields(linked_payload, entity_type=entity_type),
                    **duplicate_decision_summary,
                }
            )
            continue

        has_updates = company_action.get("mode") == "update" or child_action.get("mode") == "update"

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

    return {
        "checked_rows": checked_rows,
        "ready_rows": ready_rows,
        "ready_create_rows": ready_create_rows,
        "ready_update_rows": ready_update_rows,
        "skipped_rows": skipped_rows,
        "pending_decision_rows": pending_decision_rows,
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
    child_entity_type = get_linked_company_child_entity_type(entity_type)
    child_link_field = "COMPANY_ID"
    company_ext_key_cache: dict[str, int] = {}

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
        time.sleep(BITRIX_ROW_DELAY)

        if callable(progress_callback) and checked_rows % PROGRESS_SAVE_INTERVAL == 0:
            progress_callback(
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

        company_payload = dict(linked_payload.get("company", {}))
        ext_key = str(company_payload.pop("EXTERNAL_KEY", "") or "").strip()
        child_payload = linked_payload.get(child_entity_type, {})
        decisions = per_row_decisions if isinstance(per_row_decisions, dict) else {}
        row_decision = str(decisions.get(str(row_number), "")).strip().lower()
        if row_decision not in {"create", "update", "skip"}:
            row_decision = ""

        try:
            if ext_key and ext_key in company_ext_key_cache:
                company_action = {"mode": "cached", "record_id": company_ext_key_cache[ext_key], "meta": {}}
            elif company_payload:
                company_action = _bitrix_retry(lambda: resolve_linked_record_action_with_decision(
                    account, "company", company_payload, dedup_settings.get("company", {}),
                    row_decision,
                ))
            else:
                company_action = {"mode": "skip_payload", "record_id": None, "meta": {}}
            child_action = _bitrix_retry(lambda: resolve_linked_record_action_with_decision(
                account, child_entity_type, child_payload, dedup_settings.get(child_entity_type, {}),
                row_decision,
            )) if child_payload else {"mode": "skip_payload", "record_id": None, "meta": {}}
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
            "company": company_action,
            child_entity_type: child_action,
        }
        duplicate_decision_summary = build_linked_duplicate_decision_summary(linked_actions, entity_type)

        if company_action.get("mode") == "pending_decision" or child_action.get("mode") == "pending_decision":
            raise ValueError("Run a dry run and choose an action for each duplicate before import execution")

        if company_action.get("mode") == "skip_row" or child_action.get("mode") == "skip_row":
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

        company_id = company_action.get("record_id")
        try:
            if company_payload and company_action["mode"] != "cached":
                if company_action["mode"] == "update":
                    _bitrix_retry(lambda: update_entity_record(account, "company", company_action["record_id"], company_payload))
                elif company_action["mode"] == "create":
                    company_id = _bitrix_retry(lambda: create_entity_record(account, "company", company_payload))
            if ext_key and company_id is not None:
                company_ext_key_cache[ext_key] = company_id
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

        if company_id is not None and child_payload:
            child_payload = {
                **child_payload,
                child_link_field: normalize_record_id(company_id) or company_id,
            }

        child_record_id = child_action.get("record_id")
        try:
            if child_payload:
                if child_action["mode"] == "update":
                    _bitrix_retry(lambda: update_entity_record(account, child_entity_type, child_action["record_id"], child_payload))
                elif child_action["mode"] == "reuse" and company_id is not None and child_action["record_id"] is not None:
                    _bitrix_retry(lambda: update_entity_record(account, child_entity_type, child_action["record_id"], {child_link_field: company_id}))
                elif child_action["mode"] == "create":
                    child_record_id = _bitrix_retry(lambda: create_entity_record(account, child_entity_type, child_payload))
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

        has_child_link_update = (
            child_action.get("mode") == "reuse"
            and company_id is not None
            and child_action.get("record_id") is not None
        )
        has_updates = company_action.get("mode") == "update" or child_action.get("mode") == "update" or has_child_link_update
        linked_records = {}
        linked_entity_payloads = {
            "company": company_payload,
            child_entity_type: child_payload,
        }
        linked_entity_record_ids = {
            "company": company_id,
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
    default_field_values: dict | None = None,
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
            default_field_values=default_field_values,
        )

    invalid_row_numbers = get_invalid_row_numbers(validation_summary)
    normalized_dedup_settings = normalize_dedup_settings(dedup_settings)
    user_resolver = BitrixUserResolver(account)
    checked_rows = 0
    ready_rows = 0
    ready_create_rows = 0
    ready_update_rows = 0
    skipped_rows = 0
    pending_decision_rows = 0
    results = []

    for row_index, row_number in enumerate(row_numbers):
        if row_number < data_start_row:
            continue

        row = rows[row_index] if row_index < len(rows) else []
        if not row_has_values(row):
            continue

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
            continue

        time.sleep(BITRIX_ROW_DELAY)
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
            lambda: find_existing_record(account, entity_type, row_payload, normalized_dedup_settings)
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

    return {
        "checked_rows": checked_rows,
        "ready_rows": ready_rows,
        "ready_create_rows": ready_create_rows,
        "ready_update_rows": ready_update_rows,
        "skipped_rows": skipped_rows,
        "pending_decision_rows": pending_decision_rows,
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
    entity_config: dict | None = None,
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
    use_batch = _is_batch_eligible(entity_type, normalized_dedup_settings)
    pending_batch: list = []
    report_entity_config = (import_context or {}).get("entity_config") if isinstance(import_context, dict) else None

    def _flush_pending_batch():
        nonlocal created_rows, failed_rows
        if not pending_batch:
            return
        time.sleep(BITRIX_BATCH_DELAY)
        try:
            batch_results, batch_created, batch_failed, batch_ids = _bitrix_retry(
                lambda: _flush_crm_batch(account, entity_type, list(pending_batch))
            )
        except Exception as error:
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
            time.sleep(BITRIX_ROW_DELAY)

        if callable(progress_callback) and checked_rows % PROGRESS_SAVE_INTERVAL == 0:
            progress_callback(
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
            failed_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "failed",
                    "error": safe_format_import_error(error),
                    **build_import_result_report_meta(entity_type, entity_config=report_entity_config),
                }
            )
            continue

        if use_batch:
            pending_batch.append((row_number, row_payload))
            if len(pending_batch) >= BATCH_SIZE:
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
                lambda: find_existing_record(account, entity_type, row_payload, normalized_dedup_settings)
            )
        except Exception as error:
            failed_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "failed",
                    "error": safe_format_import_error(error),
                    **build_import_result_report_meta(
                        entity_type,
                        row_payload=row_payload,
                        entity_config=report_entity_config,
                    ),
                }
            )
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
                    _bitrix_retry(lambda: update_entity_record(account, entity_type, existing_record_id, row_payload))
                except Exception as error:
                    failed_rows += 1
                    results.append(
                        {
                            "row_number": row_number,
                            "status": "failed",
                            "error": safe_format_import_error(error),
                            **build_import_result_report_meta(
                                entity_type,
                                row_payload=row_payload,
                                record_id=existing_record_id,
                                entity_config=report_entity_config,
                            ),
                        }
                    )
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
                continue
            # row_decision == "create" → falls through to create logic below

        if existing_record_id is not None and normalized_dedup_settings["strategy"] == "update":
            try:
                _bitrix_retry(lambda: update_entity_record(account, entity_type, existing_record_id, row_payload))
            except Exception as error:
                failed_rows += 1
                results.append(
                    {
                        "row_number": row_number,
                        "status": "failed",
                        "error": safe_format_import_error(error),
                        **build_import_result_report_meta(
                            entity_type,
                            row_payload=row_payload,
                            record_id=existing_record_id,
                            entity_config=report_entity_config,
                        ),
                    }
                )
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
            continue

        try:
            record_id = _bitrix_retry(lambda: create_entity_record(account, entity_type, row_payload, context=import_context))
        except Exception as error:
            failed_rows += 1
            results.append(
                {
                    "row_number": row_number,
                    "status": "failed",
                    "error": safe_format_import_error(error),
                    **build_import_result_report_meta(
                        entity_type,
                        row_payload=row_payload,
                        entity_config=report_entity_config,
                    ),
                }
            )
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
    }
