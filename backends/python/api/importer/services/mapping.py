import re
from difflib import SequenceMatcher


NORMALIZE_RE = re.compile(r"[^a-z0-9Ѐ-ӿ]+")
TOKEN_RE = re.compile(r"[a-z0-9Ѐ-ӿ]+")
IGNORED_ID_TOKENS = {"crm", "id", "uf"}
TOKEN_ALIASES = {
    "cell": "phone",
    "cellphone": "phone",
    "telephone": "phone",
    "tel": "phone",
    "mobile": "phone",
    "town": "city",
}
TOKEN_SEQUENCE_ALIASES = {
    ("lead", "name"): ("lead", "title"),
    ("mobile", "phone"): ("phone",),
}


def normalize_mapping_value(value) -> str:
    return NORMALIZE_RE.sub("", str(value or "").strip().lower())


def extract_tokens(value, *, is_field_id: bool = False) -> list[str]:
    tokens = TOKEN_RE.findall(str(value or "").strip().lower())
    if is_field_id:
        tokens = [token for token in tokens if token not in IGNORED_ID_TOKENS]
    return tokens


def canonicalize_tokens(tokens: list[str]) -> list[str]:
    canonical_tokens = [TOKEN_ALIASES.get(token, token) for token in tokens]
    canonical_tokens = list(TOKEN_SEQUENCE_ALIASES.get(tuple(canonical_tokens), tuple(canonical_tokens)))

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


def score_fuzzy_match(header_signature: str, field_keys: dict) -> float:
    if not header_signature:
        return 0.0

    best_score = 0.0
    for candidate in (
        field_keys.get("fuzzy_title"),
        field_keys.get("fuzzy_id"),
        field_keys.get("fuzzy_linked_source_title"),
    ):
        if not candidate:
            continue
        if header_signature == candidate:
            return 1.0

        similarity = SequenceMatcher(None, header_signature, candidate).ratio()
        if similarity >= 0.9:
            best_score = max(best_score, similarity)

    return best_score


def build_field_index(fields: list[dict]) -> dict[str, dict]:
    return {
        str(field.get("id")): field
        for field in fields
        if isinstance(field, dict) and field.get("id")
    }


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


def build_candidate_mapping(headers: list[str], columns: list[str], fields: list[dict]) -> dict:
    candidates = {}
    exact_fields_by_title = {}
    exact_fields_by_id = {}
    field_match_keys = {}
    assigned_field_ids = set()
    assigned_header_indexes = set()

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
        normalized_header = normalize_mapping_value(header)
        if not normalized_header:
            continue

        field = exact_fields_by_title.get(normalized_header) or exact_fields_by_id.get(normalized_header)
        if field is None:
            continue

        field_id = str(field["id"])
        candidates[field_id] = {
            "source_header": str(header),
            "column": str(columns[index]) if index < len(columns) else "",
            "target_field": field_id,
            "match_type": "exact",
        }
        assigned_field_ids.add(field_id)
        assigned_header_indexes.add(index)

    fuzzy_matches = []
    for index, header in enumerate(headers):
        if index in assigned_header_indexes:
            continue

        header_signature = build_canonical_signature(header)
        if not header_signature:
            continue

        for field in fields:
            field_id = str(field.get("id") or "")
            if not field_id or field_id in assigned_field_ids:
                continue

            score = score_fuzzy_match(header_signature, field_match_keys.get(field_id, {}))
            if score < 0.9:
                continue

            fuzzy_matches.append(
                {
                    "field_id": field_id,
                    "header_index": index,
                    "header": str(header),
                    "column": str(columns[index]) if index < len(columns) else "",
                    "score": score,
                }
            )

    fuzzy_matches.sort(key=lambda item: (-item["score"], item["header_index"], item["field_id"]))

    for match in fuzzy_matches:
        field_id = match["field_id"]
        header_index = match["header_index"]
        if field_id in assigned_field_ids or header_index in assigned_header_indexes:
            continue

        candidates[field_id] = {
            "source_header": match["header"],
            "column": match["column"],
            "target_field": field_id,
            "match_type": "fuzzy",
        }
        assigned_field_ids.add(field_id)
        assigned_header_indexes.add(header_index)

    return candidates


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
