import re
from difflib import SequenceMatcher

from .value_normalization import build_discrete_value_keys


NORMALIZE_RE = re.compile(r"[^a-z0-9Ѐ-ӿ]+")
TOKEN_RE = re.compile(r"[a-z0-9Ѐ-ӿ]+")
IGNORED_ID_TOKENS = {"crm", "id", "uf"}
TRANSLIT_ALIAS_TOKENS = {
    "nazvanie",
    "telefon",
    "gorod",
    "pochta",
    "imya",
    "kontragent",
}
TOKEN_ALIASES = {
    "cell": "phone",
    "cellphone": "phone",
    "telephone": "phone",
    "tel": "phone",
    "mobile": "phone",
    "town": "city",
    "название": "title",
    "телефон": "phone",
    "имя": "name",
    "почта": "email",
    "емейл": "email",
    "имейл": "email",
    "город": "city",
    "источник": "source",
    "тип": "type",
    "названиекомпании": "title",
    "telefon": "phone",
    "nazvanie": "title",
    "gorod": "city",
    "pochta": "email",
    "imya": "name",
    "kontragent": "title",
}
TOKEN_SEQUENCE_ALIASES = {
    ("lead", "name"): ("lead", "title"),
    ("lead", "title"): ("title",),
    ("task", "title"): ("title",),
    ("title", "task"): ("title",),
    ("mobile", "phone"): ("phone",),
    ("e", "mail"): ("email",),
    ("эл", "почта"): ("email",),
    ("электронная", "почта"): ("email",),
    ("title", "компании"): ("title",),
    ("title", "сделки"): ("title",),
    ("title", "лида"): ("title",),
    ("title", "задачи"): ("title",),
    ("type", "сделки"): ("type",),
    ("phone", "компании"): ("phone",),
    ("phone", "контакта"): ("phone",),
    ("name", "контакта"): ("name",),
    ("email", "контакта"): ("email",),
    ("city", "компании"): ("city",),
    ("city", "контакта"): ("city",),
    ("доступна", "для", "всех"): ("opened",),
    ("доступно", "для", "всех"): ("opened",),
}
SUGGESTION_MIN_SCORE = 0.75
AUTO_MATCH_MIN_SCORE = 0.9


def normalize_mapping_value(value) -> str:
    return NORMALIZE_RE.sub("", str(value or "").strip().lower())


def extract_tokens(value, *, is_field_id: bool = False) -> list[str]:
    tokens = TOKEN_RE.findall(str(value or "").strip().lower())
    if is_field_id:
        tokens = [token for token in tokens if token not in IGNORED_ID_TOKENS]
    return tokens


def _apply_sequence_aliases(tokens: list[str]) -> list[str]:
    current = tuple(tokens)
    seen = set()
    while current in TOKEN_SEQUENCE_ALIASES and current not in seen:
        seen.add(current)
        current = tuple(TOKEN_SEQUENCE_ALIASES[current])
    return list(current)


def canonicalize_tokens(tokens: list[str]) -> list[str]:
    canonical_tokens = [TOKEN_ALIASES.get(token, token) for token in tokens]
    canonical_tokens = _apply_sequence_aliases(canonical_tokens)

    deduplicated_tokens = []
    seen_tokens = set()
    for token in canonical_tokens:
        if not token or token in seen_tokens:
            continue
        deduplicated_tokens.append(token)
        seen_tokens.add(token)

    return deduplicated_tokens


def build_canonical_signature(value, *, is_field_id: bool = False) -> str:
    return " ".join(canonicalize_tokens(extract_tokens(value, is_field_id=is_field_id)))


def build_field_match_keys(field: dict) -> dict:
    keys = {}
    raw_title = str(field.get("title") or "")
    raw_id = str(field.get("id") or "")
    linked_source_title = raw_title.split(" / ", 1)[1] if field.get("linked_entity") and " / " in raw_title else ""
    keys["exact_title"] = normalize_mapping_value(raw_title)
    keys["exact_id"] = normalize_mapping_value(raw_id)
    keys["fuzzy_title"] = build_canonical_signature(raw_title)
    keys["fuzzy_id"] = build_canonical_signature(raw_id, is_field_id=True)
    keys["exact_linked_source_title"] = normalize_mapping_value(linked_source_title)
    keys["fuzzy_linked_source_title"] = build_canonical_signature(linked_source_title)
    return keys


def _build_match_reason(header_tokens: list[str], *, alias_rule: bool = False) -> str:
    if alias_rule:
        return "alias_rule"
    if any(token in TRANSLIT_ALIAS_TOKENS for token in header_tokens):
        return "translit_alias"
    return ""


def score_fuzzy_match(header_tokens: list[str], header_signature: str, field_keys: dict) -> tuple[float, str]:
    if not header_signature:
        return 0.0, ""

    best_score = 0.0
    best_reason = ""
    for candidate in (
        field_keys.get("fuzzy_title"),
        field_keys.get("fuzzy_id"),
        field_keys.get("fuzzy_linked_source_title"),
    ):
        if not candidate:
            continue
        if header_signature == candidate:
            return 1.0, _build_match_reason(header_tokens)

        similarity = SequenceMatcher(None, header_signature, candidate).ratio()
        if similarity >= SUGGESTION_MIN_SCORE and similarity > best_score:
            best_score = similarity
            best_reason = _build_match_reason(header_tokens)

    return best_score, best_reason


def build_field_index(fields: list[dict]) -> dict[str, dict]:
    return {
        str(field.get("id")): field
        for field in fields
        if isinstance(field, dict) and field.get("id")
    }


def build_alias_rule_index(alias_rules) -> dict[str, str]:
    index = {}
    for rule in alias_rules or []:
        if not isinstance(rule, dict):
            continue
        normalized_source_label = str(rule.get("normalized_source_label") or "").strip()
        target_field_id = str(rule.get("target_field_id") or "").strip()
        if normalized_source_label and target_field_id and normalized_source_label not in index:
            index[normalized_source_label] = target_field_id
    return index


def _merge_header_candidate(match_index: dict[str, dict], match: dict) -> None:
    field_id = str(match.get("target_field") or "")
    if not field_id:
        return

    current_match = match_index.get(field_id)
    current_score = float(current_match.get("score") or 0.0) if isinstance(current_match, dict) else 0.0
    next_score = float(match.get("score") or 0.0)
    if current_match is not None and current_score >= next_score:
        return

    match_index[field_id] = dict(match)


def _serialize_suggestion(field: dict, match: dict) -> dict:
    item = {
        "target_field": str(match["target_field"]),
        "target_field_title": str(field.get("title") or match["target_field"]),
        "match_type": str(match["match_type"]),
    }
    match_reason = str(match.get("match_reason") or "").strip()
    if match_reason:
        item["match_reason"] = match_reason
    return item


def build_candidate_mapping_bundle(headers: list[str], columns: list[str], fields: list[dict], alias_rules=None) -> dict:
    field_by_id = build_field_index(fields)
    field_match_keys = {}
    exact_fields_by_title = {}
    exact_fields_by_id = {}
    alias_rule_index = build_alias_rule_index(alias_rules)
    candidates = {}
    candidate_suggestions = {}
    assigned_field_ids = set()
    assigned_header_indexes = set()
    assignable_matches = []

    for field in fields:
        field_id = str(field.get("id") or "")
        if not field_id:
            continue

        match_keys = build_field_match_keys(field)
        field_match_keys[field_id] = match_keys

        normalized_title = match_keys["exact_title"]
        normalized_id = match_keys["exact_id"]
        normalized_linked_source_title = match_keys["exact_linked_source_title"]
        if normalized_title and normalized_title not in exact_fields_by_title:
            exact_fields_by_title[normalized_title] = field
        if normalized_id and normalized_id not in exact_fields_by_id:
            exact_fields_by_id[normalized_id] = field
        if normalized_linked_source_title and normalized_linked_source_title not in exact_fields_by_title:
            exact_fields_by_title[normalized_linked_source_title] = field

    for index, header in enumerate(headers):
        column = str(columns[index]) if index < len(columns) else ""
        row_key = f"{column}:{header}"
        normalized_header = normalize_mapping_value(header)
        header_tokens = extract_tokens(header)
        header_signature = build_canonical_signature(header)
        header_match_index = {}

        if normalized_header:
            alias_field_id = alias_rule_index.get(normalized_header, "")
            alias_field = field_by_id.get(alias_field_id)
            if alias_field is not None:
                _merge_header_candidate(header_match_index, {
                    "header_index": index,
                    "source_header": str(header),
                    "column": column,
                    "target_field": alias_field_id,
                    "match_type": "alias",
                    "match_reason": _build_match_reason(header_tokens, alias_rule=True),
                    "score": 1.3,
                })

            exact_field = exact_fields_by_title.get(normalized_header) or exact_fields_by_id.get(normalized_header)
            if exact_field is not None:
                exact_field_id = str(exact_field.get("id") or "")
                if exact_field_id:
                    _merge_header_candidate(header_match_index, {
                        "header_index": index,
                        "source_header": str(header),
                        "column": column,
                        "target_field": exact_field_id,
                        "match_type": "exact",
                        "score": 1.2,
                    })

        if header_signature:
            for field in fields:
                field_id = str(field.get("id") or "")
                if not field_id:
                    continue

                score, reason = score_fuzzy_match(header_tokens, header_signature, field_match_keys.get(field_id, {}))
                if score < SUGGESTION_MIN_SCORE:
                    continue

                fuzzy_match = {
                    "header_index": index,
                    "source_header": str(header),
                    "column": column,
                    "target_field": field_id,
                    "match_type": "fuzzy",
                    "score": score,
                }
                if reason:
                    fuzzy_match["match_reason"] = reason
                _merge_header_candidate(header_match_index, fuzzy_match)

        ranked_matches = sorted(
            header_match_index.values(),
            key=lambda item: (-float(item.get("score") or 0.0), str(item.get("target_field") or "")),
        )
        if ranked_matches:
            candidate_suggestions[row_key] = [
                _serialize_suggestion(field_by_id[str(match["target_field"])], match)
                for match in ranked_matches[:3]
                if str(match.get("target_field") or "") in field_by_id
            ]

        for match in ranked_matches:
            if match["match_type"] in {"alias", "exact"} or float(match.get("score") or 0.0) >= AUTO_MATCH_MIN_SCORE:
                assignable_matches.append(match)

    assignable_matches.sort(
        key=lambda item: (-float(item.get("score") or 0.0), int(item.get("header_index") or 0), str(item.get("target_field") or "")),
    )

    for match in assignable_matches:
        field_id = str(match["target_field"])
        header_index = int(match["header_index"])
        if field_id in assigned_field_ids or header_index in assigned_header_indexes:
            continue

        candidate_item = {
            "source_header": str(match["source_header"]),
            "column": str(match["column"]),
            "target_field": field_id,
            "match_type": str(match["match_type"]),
        }
        match_reason = str(match.get("match_reason") or "").strip()
        if match_reason:
            candidate_item["match_reason"] = match_reason

        candidates[field_id] = candidate_item
        assigned_field_ids.add(field_id)
        assigned_header_indexes.add(header_index)

    return {
        "mapping": candidates,
        "suggestions": candidate_suggestions,
    }


def build_candidate_mapping(headers: list[str], columns: list[str], fields: list[dict], alias_rules=None) -> dict:
    return build_candidate_mapping_bundle(headers, columns, fields, alias_rules=alias_rules)["mapping"]


def normalize_value_mapping(value_mapping, field: dict) -> dict:
    if value_mapping in (None, ""):
        return {}

    if not isinstance(value_mapping, dict):
        raise ValueError("value_mapping must be an object")

    valid_target_values = {
        str(item.get("id") or "")
        for item in field.get("items", [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }

    normalized_value_mapping = {}
    for source_value, target_value in value_mapping.items():
        normalized_source_value = str(source_value or "").strip()
        normalized_target_value = str(target_value or "").strip()

        if not normalized_source_value:
            raise ValueError("value_mapping keys must be non-empty strings")
        if normalized_target_value not in valid_target_values:
            raise ValueError(f"Unknown mapped field value: {normalized_target_value}")

        normalized_value_mapping[normalized_source_value] = normalized_target_value

    return normalized_value_mapping


def build_field_item_value_index(field: dict) -> dict[str, str]:
    value_index = {}

    for item in field.get("items", []):
        if not isinstance(item, dict):
            continue

        item_id = str(item.get("id") or "").strip()
        item_title = str(item.get("title") or "").strip()
        if item_id:
            for index_key in build_discrete_value_keys(item_id):
                value_index.setdefault(index_key, item_id)
        if item_title:
            for index_key in build_discrete_value_keys(item_title):
                value_index.setdefault(index_key, item_id)

    return value_index


def resolve_field_item_value(field: dict, source_value) -> str:
    source_keys = build_discrete_value_keys(source_value)
    if not source_keys:
        return ""

    value_index = build_field_item_value_index(field)
    for index_key in source_keys:
        resolved_value = value_index.get(index_key)
        if resolved_value:
            return resolved_value
    return ""


def normalize_saved_mapping(mapping, headers: list[str], columns: list[str], fields: list[dict]) -> dict:
    if not isinstance(mapping, dict):
        raise ValueError("mapping must be an object")

    valid_headers = {str(header) for header in headers}
    valid_columns = {str(column) for column in columns}
    field_by_id = build_field_index(fields)
    valid_field_ids = set(field_by_id.keys())

    normalized_mapping = {}
    for mapping_key, mapping_item in mapping.items():
        if not isinstance(mapping_item, dict):
            raise ValueError("Each mapping item must be an object")

        target_field = str(mapping_item.get("target_field") or mapping_key)
        source_header = str(mapping_item.get("source_header") or "")
        column = str(mapping_item.get("column") or "")

        if target_field not in valid_field_ids:
            raise ValueError(f"Unknown target field: {target_field}")
        if source_header not in valid_headers:
            raise ValueError(f"Unknown source header: {source_header}")
        if column not in valid_columns:
            raise ValueError(f"Unknown source column: {column}")

        field = field_by_id.get(target_field, {})
        normalized_value_mapping = normalize_value_mapping(mapping_item.get("value_mapping"), field)
        normalized_mapping[target_field] = {
            "source_header": source_header,
            "column": column,
            "target_field": target_field,
        }
        if normalized_value_mapping:
            normalized_mapping[target_field]["value_mapping"] = normalized_value_mapping

    return normalized_mapping
