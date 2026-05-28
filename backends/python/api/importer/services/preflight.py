from .b24_fields import SMART_PROCESS_ENTITY_TYPE
from .mapping import resolve_field_item_value
from .import_execution import (
    build_linked_record_title,
    build_linked_mapping_groups,
    build_linked_row_payload,
    get_linked_parent_entity_type,
    is_linked_import_entity_type,
    normalize_entity_dedup_settings,
)
from .validation import CRM_ACTIVITY_COMMUNICATION_TYPES, resolve_row_field_value


_RUNTIME_OPTIONAL_REQUIRED_FIELDS = {
    "task": {"RESPONSIBLE_ID", "CREATED_BY"},
    "task_comment": {"AUTHOR_ID"},
}

# crm.item.fields возвращает isRequired=true для полей вроде opened, stageId, categoryId,
# но crm.item.add принимает их без явной передачи — у Bitrix24 есть дефолты.
# Единственное поле, которое Bitrix24 реально требует при создании элемента — title.
_SMART_PROCESS_REQUIRED_FIELDS = frozenset({"title"})


def _build_issue(code: str, severity: str, **payload) -> dict:
    return {
        "code": code,
        "severity": severity,
        **payload,
    }


def _build_required_field_issues(entity_type: str, fields: list[dict], mapping: dict, default_field_values: dict | None) -> list[dict]:
    mapped_field_ids = {
        str(target_field)
        for target_field, mapping_item in (mapping or {}).items()
        if isinstance(mapping_item, dict)
    }
    default_field_ids = {
        str(field_id)
        for field_id in (default_field_values or {}).keys()
        if str(field_id or "").strip()
    }

    issues = []
    normalized_entity_type = str(entity_type or "").strip()
    is_smart_process = normalized_entity_type == SMART_PROCESS_ENTITY_TYPE
    runtime_optional_required_fields = _RUNTIME_OPTIONAL_REQUIRED_FIELDS.get(normalized_entity_type, set())

    for field in fields:
        field_id = str(field.get("id") or "").strip()
        if not field_id:
            continue
        if is_smart_process:
            if field_id not in _SMART_PROCESS_REQUIRED_FIELDS:
                continue
        else:
            if not field.get("required"):
                continue
            if field_id in runtime_optional_required_fields:
                continue
        if field_id in mapped_field_ids or field_id in default_field_ids:
            continue
        issues.append(_build_issue(
            "required_field_unmapped",
            "error",
            field_id=field_id,
        ))
    return issues


def _build_field_index(fields: list[dict]) -> dict[str, dict]:
    return {
        str(field.get("id") or "").strip(): field
        for field in fields
        if isinstance(field, dict) and str(field.get("id") or "").strip()
    }


def _collect_unique_non_empty_values(values: list[object]) -> list[str]:
    unique_values = []
    seen_values = set()

    for value in values:
        normalized_value = str(value or "").strip()
        if not normalized_value or normalized_value in seen_values:
            continue
        seen_values.add(normalized_value)
        unique_values.append(normalized_value)

    return unique_values


def _build_column_index_by_name(columns: list[str]) -> dict[str, int]:
    return {
        str(column or "").strip(): index
        for index, column in enumerate(columns or [])
        if str(column or "").strip()
    }


def _iter_data_rows(rows: list[list], row_numbers: list[int], data_start_row: int):
    for row_index, row_number in enumerate(row_numbers):
        if row_number < data_start_row:
            continue
        yield rows[row_index] if row_index < len(rows) else [], row_number


def _field_supports_discrete_values(field: dict) -> bool:
    field_type = str(field.get("type") or "").strip().lower()
    if field_type in {"crm_status", "enumeration", "list", "select"}:
        return True
    return isinstance(field.get("items"), list) and bool(field.get("items"))


def _build_choice_value_issues(
    *,
    rows: list[list],
    row_numbers: list[int],
    columns: list[str],
    data_start_row: int,
    mapping: dict,
    fields: list[dict],
) -> list[dict]:
    if not isinstance(mapping, dict) or not mapping:
        return []

    field_by_id = _build_field_index(fields)
    column_index_by_name = _build_column_index_by_name(columns)
    issues = []

    for field_id, mapping_item in mapping.items():
        if not isinstance(mapping_item, dict):
            continue

        normalized_field_id = str(field_id or "").strip()
        field = field_by_id.get(normalized_field_id, {})
        if not _field_supports_discrete_values(field):
            continue

        column_index = column_index_by_name.get(str(mapping_item.get("column") or "").strip())
        if column_index is None:
            continue

        observed_values = _collect_unique_non_empty_values([
            row[column_index] if column_index < len(row) else ""
            for row, _row_number in _iter_data_rows(rows, row_numbers, data_start_row)
        ])
        if not observed_values:
            continue

        field_items = field.get("items") if isinstance(field.get("items"), list) else []
        if not field_items:
            issues.append(_build_issue(
                "field_options_unavailable",
                "error",
                field_id=normalized_field_id,
                value_count=len(observed_values),
                values=observed_values,
            ))
            continue

        value_mapping = mapping_item.get("value_mapping") if isinstance(mapping_item, dict) else None
        mapped_source_values = {
            str(source_value).strip()
            for source_value, target_value in (value_mapping or {}).items()
            if str(source_value).strip() and str(target_value).strip()
        }
        unmapped_values = [
            source_value
            for source_value in observed_values
            if source_value not in mapped_source_values and not resolve_field_item_value(field, source_value)
        ]
        if not unmapped_values:
            continue

        issues.append(_build_issue(
            "field_values_unmapped",
            "error",
            field_id=normalized_field_id,
            value_count=len(unmapped_values),
            values=unmapped_values,
        ))

    return issues


def _build_dedup_issues(entity_type: str, mapping: dict, fields: list[dict], dedup_settings, default_field_values: dict | None) -> list[dict]:
    normalized_defaults = {
        str(field_id).upper()
        for field_id in (default_field_values or {}).keys()
        if str(field_id or "").strip()
    }
    normalized_dedup = normalize_entity_dedup_settings(entity_type, dedup_settings)
    issues = []

    if is_linked_import_entity_type(entity_type):
        grouped_mapping = build_linked_mapping_groups(mapping, fields, entity_type=entity_type)
        for linked_entity, entity_dedup_settings in normalized_dedup.items():
            mapped_fields = {k.upper() for k in grouped_mapping.get(str(linked_entity), {}).keys()}
            for field_id in entity_dedup_settings.get("fields", []):
                normalized_field_id = str(field_id or "").strip().upper()
                if not normalized_field_id or normalized_field_id in mapped_fields or normalized_field_id in normalized_defaults:
                    continue
                issues.append(_build_issue(
                    "dedup_field_unmapped",
                    "error",
                    entity=str(linked_entity),
                    field_id=normalized_field_id,
                ))
        return issues

    mapped_fields = {
        str(target_field).upper()
        for target_field, mapping_item in (mapping or {}).items()
        if isinstance(mapping_item, dict)
    }
    for field_id in normalized_dedup.get("fields", []):
        normalized_field_id = str(field_id or "").strip().upper()
        if not normalized_field_id or normalized_field_id in mapped_fields or normalized_field_id in normalized_defaults:
            continue
        issues.append(_build_issue(
            "dedup_field_unmapped",
            "error",
            field_id=normalized_field_id,
        ))

    return issues


def _build_linked_identity_warnings(
    *,
    entity_type: str,
    rows: list[list],
    row_numbers: list[int],
    columns: list[str],
    data_start_row: int,
    mapping: dict,
    fields: list[dict],
    dedup_settings,
) -> list[dict]:
    if not is_linked_import_entity_type(entity_type):
        return []

    parent_entity_type = get_linked_parent_entity_type(entity_type)
    grouped_mapping = build_linked_mapping_groups(mapping, fields, entity_type=entity_type)
    parent_mapping = grouped_mapping.get(parent_entity_type, {})
    if not parent_mapping or "XML_ID" in parent_mapping or "EXTERNAL_KEY" in parent_mapping:
        return []

    normalized_dedup = normalize_entity_dedup_settings(entity_type, dedup_settings)
    parent_dedup_fields = set((normalized_dedup.get(parent_entity_type) or {}).get("fields", []))
    if parent_dedup_fields.intersection(parent_mapping.keys()):
        return []

    title_counts = {}
    for row_index, row_number in enumerate(row_numbers):
        if row_number < data_start_row:
            continue

        row = rows[row_index] if row_index < len(rows) else []
        linked_payload = build_linked_row_payload(
            row,
            columns,
            mapping,
            fields,
            entity_type=entity_type,
        )
        parent_payload = linked_payload.get(parent_entity_type, {})
        parent_title = build_linked_record_title(parent_entity_type, parent_payload)
        if not parent_title:
            continue
        title_counts[parent_title] = title_counts.get(parent_title, 0) + 1

    repeated_row_count = sum(count for count in title_counts.values() if count > 1)
    if repeated_row_count < 2:
        return []

    return [
        _build_issue(
            f"linked_{parent_entity_type}_identity_missing",
            "warning",
            entity=parent_entity_type,
            row_count=repeated_row_count,
        ),
    ]


def _build_crm_activity_communications_issues(
    *,
    entity_type: str,
    rows: list[list],
    row_numbers: list[int],
    columns: list[str],
    data_start_row: int,
    mapping: dict,
    fields: list[dict],
    default_field_values: dict | None,
) -> list[dict]:
    if entity_type != "crm_activity":
        return []

    field_by_id = _build_field_index(fields)
    if "TYPE_ID" not in field_by_id or "COMMUNICATIONS_VALUE" not in field_by_id:
        return []

    column_index_by_name = _build_column_index_by_name(columns)
    missing_row_count = 0
    activity_types = []
    seen_activity_types = set()

    for row, _row_number in _iter_data_rows(rows, row_numbers, data_start_row):
        type_id, _type_column, _type_source_header = resolve_row_field_value(
            row=row,
            column_index_by_name=column_index_by_name,
            mapping=mapping,
            field_by_id=field_by_id,
            default_field_values=default_field_values,
            target_field="TYPE_ID",
        )
        activity_kind = CRM_ACTIVITY_COMMUNICATION_TYPES.get(type_id)
        if activity_kind is None:
            continue

        communication_value, _column, _source_header = resolve_row_field_value(
            row=row,
            column_index_by_name=column_index_by_name,
            mapping=mapping,
            field_by_id=field_by_id,
            default_field_values=default_field_values,
            target_field="COMMUNICATIONS_VALUE",
        )
        if communication_value:
            continue

        missing_row_count += 1
        if activity_kind not in seen_activity_types:
            seen_activity_types.add(activity_kind)
            activity_types.append(activity_kind)

    if missing_row_count == 0:
        return []

    return [
        _build_issue(
            "crm_activity_communications_missing",
            "error",
            field_id="COMMUNICATIONS_VALUE",
            row_count=missing_row_count,
            activity_types=activity_types,
        ),
    ]


def build_mapping_preflight(
    *,
    entity_type: str,
    rows: list[list],
    row_numbers: list[int],
    columns: list[str],
    data_start_row: int,
    mapping: dict,
    fields: list[dict],
    dedup_settings,
    default_field_values: dict | None = None,
) -> dict:
    issues = []
    issues.extend(_build_required_field_issues(entity_type, fields, mapping, default_field_values))
    issues.extend(_build_dedup_issues(entity_type, mapping, fields, dedup_settings, default_field_values))
    issues.extend(_build_choice_value_issues(
        rows=rows,
        row_numbers=row_numbers,
        columns=columns,
        data_start_row=data_start_row,
        mapping=mapping,
        fields=fields,
    ))
    issues.extend(_build_crm_activity_communications_issues(
        entity_type=entity_type,
        rows=rows,
        row_numbers=row_numbers,
        columns=columns,
        data_start_row=data_start_row,
        mapping=mapping,
        fields=fields,
        default_field_values=default_field_values,
    ))
    issues.extend(_build_linked_identity_warnings(
        entity_type=entity_type,
        rows=rows,
        row_numbers=row_numbers,
        columns=columns,
        data_start_row=data_start_row,
        mapping=mapping,
        fields=fields,
        dedup_settings=dedup_settings,
    ))

    blocking_issue_count = sum(1 for issue in issues if str(issue.get("severity") or "") == "error")
    warning_count = sum(1 for issue in issues if str(issue.get("severity") or "") == "warning")

    return {
        "blocking_issue_count": blocking_issue_count,
        "warning_count": warning_count,
        "issues": issues,
    }
