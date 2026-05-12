import re


TASK_USER_REFERENCE_FIELDS = {
    "AUTHOR_ID",
    "RESPONSIBLE_ID",
    "ACCOMPLICES",
    "AUDITORS",
    "CREATED_BY",
}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USER_LOOKUP_SELECT = ["ID", "EMAIL", "LOGIN", "XML_ID"]
USER_LIST_SELECT = ["ID", "NAME", "LAST_NAME", "EMAIL", "LOGIN", "XML_ID"]


def normalize_value(value) -> str:
    return str(value or "").strip()


def normalize_compare_value(value) -> str:
    return normalize_value(value).lower()


def is_task_user_reference_field(field: dict | None, target_field: str = "") -> bool:
    field_id = str((field or {}).get("id") or target_field or "").upper()
    return field_id in TASK_USER_REFERENCE_FIELDS


def unwrap_bitrix_result(response):
    return getattr(response, "result", response)


def extract_user_items(result) -> list[dict]:
    if isinstance(result, dict):
        items = result.get("items")
        if not isinstance(items, list):
            items = result.get("result")
        if not isinstance(items, list):
            items = result.get("users")
    else:
        items = result

    if not isinstance(items, list):
        return []

    return [item for item in items if isinstance(item, dict)]


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


class BitrixUserResolver:
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

        resolved_user_id = self._resolve_without_cache(normalized_value)
        self._cache[cache_key] = resolved_user_id
        return resolved_user_id

    def _resolve_without_cache(self, value: str) -> int | None:
        if re.fullmatch(r"\d+", value):
            parsed_value = int(value)
            return parsed_value if parsed_value > 0 else None

        for field_name, field_value in self._build_lookup_candidates(value):
            resolved_user_id = self._lookup_user_id(field_name, field_value)
            if resolved_user_id is not None:
                return resolved_user_id

        return None

    def _build_lookup_candidates(self, value: str) -> list[tuple[str, str]]:
        if EMAIL_RE.match(value):
            return [("EMAIL", value)]

        return [
            ("LOGIN", value),
            ("XML_ID", value),
        ]

    def _get_user_lookup_method(self):
        client = getattr(self.account, "client", None)
        user_scope = getattr(client, "user", None)
        if user_scope is None:
            raise ValueError("Bitrix user lookup method is unavailable")

        lookup_method = getattr(user_scope, "get", None) or getattr(user_scope, "list", None)
        if lookup_method is None:
            raise ValueError("Bitrix user lookup method is unavailable")

        return lookup_method

    def _lookup_user_id(self, field_name: str, field_value: str) -> int | None:
        lookup_method = self._get_user_lookup_method()
        response = invoke_with_fallbacks(
            [
                lambda: lookup_method(filter={field_name: field_value}, select=USER_LOOKUP_SELECT),
                lambda: lookup_method({field_name: field_value}, USER_LOOKUP_SELECT),
                lambda: lookup_method(filter={field_name: field_value}),
                lambda: lookup_method({field_name: field_value}),
            ]
        )
        for item in extract_user_items(unwrap_bitrix_result(response)):
            user_id = item.get("ID") or item.get("id")
            try:
                return int(user_id)
            except (TypeError, ValueError):
                continue

        return None


def build_bitrix_user_option_label(user: dict) -> str:
    user_id = normalize_value(user.get("ID") or user.get("id"))
    email = normalize_value(user.get("EMAIL") or user.get("email"))
    login = normalize_value(user.get("LOGIN") or user.get("login"))
    first_name = normalize_value(user.get("NAME") or user.get("name"))
    last_name = normalize_value(user.get("LAST_NAME") or user.get("last_name"))
    full_name = normalize_value(f"{first_name} {last_name}")

    parts = []
    if full_name:
        parts.append(full_name)
    if email:
        parts.append(email)
    elif login:
        parts.append(login)
    if user_id:
        parts.append(f"ID {user_id}")

    return " · ".join(parts) or user_id


def list_bitrix_users(account) -> list[dict]:
    resolver = BitrixUserResolver(account)
    lookup_method = resolver._get_user_lookup_method()
    response = invoke_with_fallbacks(
        [
            lambda: lookup_method(filter={}, select=USER_LIST_SELECT),
            lambda: lookup_method({}, USER_LIST_SELECT),
            lambda: lookup_method(filter={}),
            lambda: lookup_method({}),
        ]
    )

    options = []
    seen_user_ids = set()
    for item in extract_user_items(unwrap_bitrix_result(response)):
        user_id = normalize_value(item.get("ID") or item.get("id"))
        if not user_id or user_id in seen_user_ids:
            continue

        seen_user_ids.add(user_id)
        options.append(
            {
                "value": user_id,
                "label": build_bitrix_user_option_label(item),
            }
        )

    return sorted(options, key=lambda option: option["label"].lower())
