import re


TASK_REFERENCE_FIELDS = {
    "PARENT_ID",
    "TASK_ID",
}
TASK_LOOKUP_SELECT = ["ID", "XML_ID"]


def normalize_value(value) -> str:
    return str(value or "").strip()


def normalize_compare_value(value) -> str:
    return normalize_value(value).lower()


def is_task_reference_field(field: dict | None, target_field: str = "") -> bool:
    field_id = str((field or {}).get("id") or target_field or "").upper()
    return field_id in TASK_REFERENCE_FIELDS


def unwrap_bitrix_result(response):
    return getattr(response, "result", response)


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


class BitrixTaskResolver:
    def __init__(self, account):
        self.account = account
        self._cache: dict[str, int | None] = {}

    def resolve(self, value) -> int | None:
        normalized_value = normalize_value(value)
        if not normalized_value:
            return None

        cache_key = normalize_compare_value(normalized_value)
        if cache_key in self._cache:
            return self._cache[cache_key]

        resolved_task_id = self._resolve_without_cache(normalized_value)
        self._cache[cache_key] = resolved_task_id
        return resolved_task_id

    def _resolve_without_cache(self, value: str) -> int | None:
        if re.fullmatch(r"\d+", value):
            parsed_value = int(value)
            return parsed_value if parsed_value > 0 else None

        return self._lookup_task_id("XML_ID", value)

    def _get_task_lookup_method(self):
        client = getattr(self.account, "client", None)
        tasks_root = getattr(client, "tasks", None)
        task_scope = getattr(tasks_root, "task", None) or getattr(tasks_root, "tasks", None)
        if task_scope is None:
            raise ValueError("Bitrix task lookup method is unavailable")

        lookup_method = getattr(task_scope, "list", None)
        if lookup_method is None:
            raise ValueError("Bitrix task lookup method is unavailable")

        return lookup_method

    def _lookup_task_id(self, field_name: str, field_value: str) -> int | None:
        lookup_method = self._get_task_lookup_method()
        response = invoke_with_fallbacks(
            [
                lambda: lookup_method(filter={field_name: field_value}, select=TASK_LOOKUP_SELECT),
                lambda: lookup_method({field_name: field_value}, TASK_LOOKUP_SELECT),
                lambda: lookup_method(filter={field_name: field_value}),
                lambda: lookup_method({field_name: field_value}),
            ]
        )
        result = unwrap_bitrix_result(response)

        if isinstance(result, dict):
            items = result.get("items")
            if not isinstance(items, list):
                items = result.get("result")
            if not isinstance(items, list):
                items = result.get("tasks")
        else:
            items = result

        if not isinstance(items, list):
            return None

        for item in items:
            if not isinstance(item, dict):
                continue

            task_id = item.get("ID") or item.get("id")
            try:
                return int(task_id)
            except (TypeError, ValueError):
                continue

        return None
