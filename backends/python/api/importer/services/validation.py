import re
from datetime import datetime

from .task_resolution import BitrixTaskResolver, is_task_reference_field
from .user_resolution import BitrixUserResolver, is_task_user_reference_field


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_ALLOWED_RE = re.compile(r"^[\d+\-().\s]+$")
MULTI_VALUE_SPLIT_RE = re.compile(r"[;\n]+")
BOOLEAN_VALUES = {"1", "0", "true", "false", "yes", "no", "y", "n", "да", "нет"}
BOOLEAN_TRUE_VALUES = {"1", "true", "yes", "y", "да"}
BOOLEAN_FALSE_VALUES = {"0", "false", "no", "n", "нет"}
DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
)
DATETIME_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
)
BITRIX_MULTIFIELD_VALIDATORS = {
    "PHONE": "phone",
    "EMAIL": "email",
}


def normalize_value(value) -> str:
    return str(value or "").strip()


def normalize_compare_value(value) -> str:
    return normalize_value(value).lower()


def resolve_default_field_value(default_field_values: dict | None, target_field: str) -> str:
    if not isinstance(default_field_values, dict):
        return ""

    return normalize_value(default_field_values.get(str(target_field or "")))


def split_field_values(field: dict, value: str) -> list[str]:
    normalized_value = normalize_value(value)
    if not normalized_value:
        return []

    if not field.get("multiple"):
        return [normalized_value]

    split_values = [
        normalize_value(item)
        for item in MULTI_VALUE_SPLIT_RE.split(normalized_value)
    ]
    normalized_values = [item for item in split_values if item]
    return normalized_values or [normalized_value]


def row_has_values(row_values) -> bool:
    return any(normalize_value(value) for value in row_values)


def is_valid_phone(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    return len(digits) >= 5 and bool(PHONE_ALLOWED_RE.match(value))


def parse_date_value(value: str):
    normalized_value = normalize_value(value)
    if not normalized_value:
        raise ValueError("Date value is required")

    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(normalized_value, date_format)
        except ValueError:
            continue

    raise ValueError("Invalid date value")


def parse_datetime_value(value: str):
    normalized_value = normalize_value(value)
    if not normalized_value:
        raise ValueError("Datetime value is required")

    for datetime_format in DATETIME_FORMATS:
        try:
            return datetime.strptime(normalized_value, datetime_format)
        except ValueError:
            continue

    return parse_date_value(normalized_value)


def parse_integer_value(value: str) -> int:
    return int(normalize_value(value))


def parse_number_value(value: str) -> float:
    return float(normalize_value(value).replace(",", "."))


def parse_boolean_value(value: str) -> int:
    normalized_value = normalize_compare_value(value)
    if normalized_value in BOOLEAN_TRUE_VALUES:
        return 1
    if normalized_value in BOOLEAN_FALSE_VALUES:
        return 0
    raise ValueError("Invalid boolean value")


def is_valid_date(value: str) -> bool:
    try:
        parse_date_value(value)
        return True
    except ValueError:
        return False


def is_valid_datetime(value: str) -> bool:
    try:
        parse_datetime_value(value)
        return True
    except ValueError:
        return False


def is_valid_integer(value: str) -> bool:
    try:
        parse_integer_value(value)
        return True
    except ValueError:
        return False


def is_valid_number(value: str) -> bool:
    try:
        parse_number_value(value)
        return True
    except ValueError:
        return False


def build_issue(row_number: int, column: str, source_header: str, target_field: str, code: str, message: str, value: str) -> dict:
    return {
        "row_number": row_number,
        "column": column,
        "source_header": source_header,
        "target_field": target_field,
        "code": code,
        "message": message,
        "value": value,
    }


def build_field_items_index(field: dict) -> dict[str, str]:
    items_index = {}

    for item in field.get("items", []):
        if not isinstance(item, dict):
            continue

        item_id = normalize_value(item.get("id"))
        item_title = normalize_value(item.get("title"))
        if item_id:
            items_index[normalize_compare_value(item_id)] = item_id
        if item_title:
            items_index[normalize_compare_value(item_title)] = item_id

    return items_index


def resolve_mapped_field_value(field: dict, value: str, mapping_item: dict | None = None) -> str:
    normalized_value = normalize_value(value)
    if not normalized_value:
        return ""

    value_mapping = mapping_item.get("value_mapping") if isinstance(mapping_item, dict) else None
    if isinstance(value_mapping, dict):
        mapped_value = normalize_value(value_mapping.get(normalized_value))
        if mapped_value:
            return mapped_value

    items_index = build_field_items_index(field)
    return items_index.get(normalize_compare_value(normalized_value), "")


COLUMN_TYPE_OVERRIDES = {"string", "integer", "double", "date", "datetime", "boolean"}


def resolve_field_validation_type(field: dict, target_field: str, column_type_override: str = "") -> str:
    override = str(column_type_override or "").strip().lower()
    if override in COLUMN_TYPE_OVERRIDES:
        return override

    field_type = str(field.get("type") or "string").lower()
    if field_type != "crm_multifield":
        return field_type

    field_id = str(field.get("id") or target_field or "").upper()
    return BITRIX_MULTIFIELD_VALIDATORS.get(field_id, field_type)


def validate_field_value(
    field: dict,
    value: str,
    row_number: int,
    column: str,
    source_header: str,
    target_field: str,
    mapping_item: dict | None = None,
    account=None,
    user_resolver: BitrixUserResolver | None = None,
    task_resolver: BitrixTaskResolver | None = None,
):
    field_title = str(field.get("title") or target_field)
    column_type_override = str((mapping_item or {}).get("column_type") or "").strip().lower()
    field_type = resolve_field_validation_type(field, target_field, column_type_override)
    task_user_resolver = user_resolver or (BitrixUserResolver(account) if account is not None else None)
    bitrix_task_resolver = task_resolver or (BitrixTaskResolver(account) if account is not None else None)

    if field.get("required") and not value:
        return build_issue(
            row_number,
            column,
            source_header,
            target_field,
            "required",
            f'Field "{field_title}" is required',
            value,
        )

    if not value:
        return None

    for item_value in split_field_values(field, value):
        if field.get("items"):
            mapped_value = resolve_mapped_field_value(field, item_value, mapping_item)
            if not mapped_value:
                return build_issue(
                    row_number,
                    column,
                    source_header,
                    target_field,
                    "enum",
                    f'Field "{field_title}" must contain a mapped list value',
                    item_value,
                )

        if is_task_user_reference_field(field, target_field) and task_user_resolver is not None:
            if task_user_resolver.resolve(item_value) is None:
                return build_issue(
                    row_number,
                    column,
                    source_header,
                    target_field,
                    "user",
                    f'Field "{field_title}" must contain a valid Bitrix user reference',
                    item_value,
                )
            continue

        if is_task_reference_field(field, target_field) and bitrix_task_resolver is not None:
            if bitrix_task_resolver.resolve(item_value) is None:
                return build_issue(
                    row_number,
                    column,
                    source_header,
                    target_field,
                    "task",
                    f'Field "{field_title}" must contain a valid Bitrix task reference',
                    item_value,
                )
            continue

        if field_type == "email" and not EMAIL_RE.match(item_value):
            return build_issue(
                row_number,
                column,
                source_header,
                target_field,
                "email",
                f'Field "{field_title}" must contain a valid email',
                item_value,
            )

        if field_type == "phone" and not is_valid_phone(item_value):
            return build_issue(
                row_number,
                column,
                source_header,
                target_field,
                "phone",
                f'Field "{field_title}" must contain a valid phone',
                item_value,
            )

        if field_type == "date" and not is_valid_date(item_value):
            return build_issue(
                row_number,
                column,
                source_header,
                target_field,
                "date",
                f'Field "{field_title}" must contain a valid date',
                item_value,
            )

        if field_type == "datetime" and not is_valid_datetime(item_value):
            return build_issue(
                row_number,
                column,
                source_header,
                target_field,
                "datetime",
                f'Field "{field_title}" must contain a valid date/time',
                item_value,
            )

        if field_type in {"integer", "int"} and not is_valid_integer(item_value):
            return build_issue(
                row_number,
                column,
                source_header,
                target_field,
                "integer",
                f'Field "{field_title}" must contain a whole number',
                item_value,
            )

        if field_type in {"double", "float", "money", "number"} and not is_valid_number(item_value):
            return build_issue(
                row_number,
                column,
                source_header,
                target_field,
                "number",
                f'Field "{field_title}" must contain a valid number',
                item_value,
            )

        if field_type in {"boolean", "bool"} and item_value.lower() not in BOOLEAN_VALUES:
            return build_issue(
                row_number,
                column,
                source_header,
                target_field,
                "boolean",
                f'Field "{field_title}" must contain a valid boolean value',
                item_value,
            )

    return None


def build_validation_result(
    *,
    rows: list[list],
    row_numbers: list[int],
    columns: list[str],
    data_start_row: int,
    mapping: dict,
    fields: list[dict],
    account=None,
    default_field_values: dict | None = None,
) -> dict:
    column_index_by_name = {
        str(column): index
        for index, column in enumerate(columns)
    }
    field_by_id = {
        str(field.get("id")): field
        for field in fields
        if isinstance(field, dict) and field.get("id")
    }

    issues = []
    invalid_row_numbers = set()
    checked_rows = 0
    user_resolver = BitrixUserResolver(account) if account is not None else None
    task_resolver = BitrixTaskResolver(account) if account is not None else None

    for row_index, row_number in enumerate(row_numbers):
        if row_number < data_start_row:
            continue

        row = rows[row_index] if row_index < len(rows) else []
        if not row_has_values(row):
            continue

        checked_rows += 1

        for target_field, mapping_item in mapping.items():
            if not isinstance(mapping_item, dict):
                continue

            field = field_by_id.get(str(target_field))
            if field is None:
                continue

            column = str(mapping_item.get("column") or "")
            source_header = str(mapping_item.get("source_header") or "")
            column_index = column_index_by_name.get(column)
            value = ""
            if column_index is not None and column_index < len(row):
                value = normalize_value(row[column_index])
            if not value:
                value = resolve_default_field_value(default_field_values, str(target_field))

            issue = validate_field_value(
                field=field,
                value=value,
                row_number=row_number,
                column=column,
                source_header=source_header,
                target_field=str(target_field),
                mapping_item=mapping_item,
                account=account,
                user_resolver=user_resolver,
                task_resolver=task_resolver,
            )
            if issue is not None:
                issues.append(issue)
                invalid_row_numbers.add(row_number)

    return {
        "checked_rows": checked_rows,
        "valid_rows": checked_rows - len(invalid_row_numbers),
        "invalid_rows": len(invalid_row_numbers),
        "issue_count": len(issues),
        "issues": issues,
    }
