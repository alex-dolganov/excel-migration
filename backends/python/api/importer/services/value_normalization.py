import re
from datetime import datetime


WHITESPACE_RE = re.compile(r"\s+")
COMPACT_RE = re.compile(r"[^0-9a-zа-яё]+", re.IGNORECASE)
PHONE_ALLOWED_RE = re.compile(r"^[\d+\-().\s]+$")
CURRENCY_CODE_RE = re.compile(r"^[A-Z]{3}$")

BOOLEAN_TRUE_VALUES = frozenset({"1", "true", "yes", "y", "да"})
BOOLEAN_FALSE_VALUES = frozenset({"0", "false", "no", "n", "нет"})
CURRENCY_ID_ALIASES = {
    "rub": "RUB",
    "rur": "RUB",
    "руб": "RUB",
    "рубль": "RUB",
    "рубли": "RUB",
    "российский рубль": "RUB",
    "usd": "USD",
    "доллар": "USD",
    "доллары": "USD",
    "доллар сша": "USD",
    "eur": "EUR",
    "евро": "EUR",
}
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
SEMANTIC_VALUE_ALIASES = {
    "advertising": frozenset({
        "advertising",
        "advertisement",
        "ad",
        "ads",
        "реклама",
        "рекламная",
        "рекламный",
    }),
    "other": frozenset({
        "other",
        "others",
        "другое",
        "прочее",
    }),
}


def normalize_text_value(value) -> str:
    normalized_value = str(value or "").strip().casefold()
    if not normalized_value:
        return ""
    return WHITESPACE_RE.sub(" ", normalized_value)


def compact_text_value(value) -> str:
    return COMPACT_RE.sub("", normalize_text_value(value))


def normalize_currency_code(value) -> str:
    normalized_value = normalize_text_value(value)
    if not normalized_value:
        return ""

    alias_value = CURRENCY_ID_ALIASES.get(normalized_value)
    if alias_value:
        return alias_value

    uppercase_value = str(value or "").strip().upper()
    if CURRENCY_CODE_RE.match(uppercase_value):
        return uppercase_value

    return ""


def _build_semantic_value_alias_index() -> dict[str, str]:
    index = {}
    for canonical_value, aliases in SEMANTIC_VALUE_ALIASES.items():
        for alias in aliases:
            normalized_alias = normalize_text_value(alias)
            compact_alias = compact_text_value(alias)
            if normalized_alias:
                index[normalized_alias] = canonical_value
            if compact_alias:
                index[compact_alias] = canonical_value
    return index


SEMANTIC_VALUE_ALIAS_INDEX = _build_semantic_value_alias_index()


def _normalize_boolean_key(value) -> str:
    normalized_value = normalize_text_value(value)
    if normalized_value in BOOLEAN_TRUE_VALUES:
        return "1"
    if normalized_value in BOOLEAN_FALSE_VALUES:
        return "0"
    return ""


def _normalize_phone_key(value) -> str:
    raw_value = str(value or "").strip()
    if not raw_value or not PHONE_ALLOWED_RE.match(raw_value):
        return ""

    digits = re.sub(r"\D", "", raw_value)
    if len(digits) < 5:
        return ""

    return digits


def _build_datetime_keys(value) -> set[str]:
    raw_value = str(value or "").strip()
    if not raw_value:
        return set()

    for datetime_format in DATETIME_FORMATS:
        try:
            parsed_value = datetime.strptime(raw_value, datetime_format)
        except ValueError:
            continue
        return {
            f"date:{parsed_value.strftime('%Y-%m-%d')}",
            f"datetime:{parsed_value.strftime('%Y-%m-%dT%H:%M:%S')}",
        }

    for date_format in DATE_FORMATS:
        try:
            parsed_value = datetime.strptime(raw_value, date_format)
        except ValueError:
            continue
        return {f"date:{parsed_value.strftime('%Y-%m-%d')}"}

    return set()


def build_discrete_value_keys(value) -> set[str]:
    normalized_value = normalize_text_value(value)
    if not normalized_value:
        return set()

    compact_value = compact_text_value(value)
    keys = {f"text:{normalized_value}"}
    if compact_value:
        keys.add(f"compact:{compact_value}")

    boolean_key = _normalize_boolean_key(value)
    if boolean_key:
        keys.add(f"boolean:{boolean_key}")

    currency_code = normalize_currency_code(value)
    if currency_code:
        keys.add(f"currency:{currency_code}")

    phone_key = _normalize_phone_key(value)
    if phone_key:
        keys.add(f"phone:{phone_key}")

    semantic_alias = SEMANTIC_VALUE_ALIAS_INDEX.get(normalized_value) or SEMANTIC_VALUE_ALIAS_INDEX.get(compact_value)
    if semantic_alias:
        keys.add(f"semantic:{semantic_alias}")

    keys.update(_build_datetime_keys(value))
    return keys


def resolve_value_mapping(value_mapping, source_value) -> str:
    if not isinstance(value_mapping, dict):
        return ""

    normalized_source_value = str(source_value or "").strip()
    if not normalized_source_value:
        return ""

    exact_match = str(value_mapping.get(normalized_source_value) or "").strip()
    if exact_match:
        return exact_match

    source_keys = build_discrete_value_keys(normalized_source_value)
    if not source_keys:
        return ""

    for mapping_source_value, target_value in value_mapping.items():
        normalized_target_value = str(target_value or "").strip()
        if not normalized_target_value:
            continue

        if source_keys.intersection(build_discrete_value_keys(mapping_source_value)):
            return normalized_target_value

    return ""
