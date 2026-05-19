from django.utils import timezone

from .b24_fields import SMART_PROCESS_ENTITY_TYPE, get_linked_import_schema
from .validation import normalize_value


REPORT_ENTITY_LABELS = {
    "lead": "Лид",
    "contact": "Контакт",
    "company": "Компания",
    "deal": "Сделка",
    "task": "Задача",
    "task_comment": "Комментарий задачи",
    "task_checklist_item": "Пункт чек-листа",
    "task_attachment": "Вложение задачи",
    "crm_activity": "Активность CRM",
    "crm_note": "Заметка CRM",
    "crm_files_lead": "Файл CRM: лид",
    "crm_files_contact": "Файл CRM: контакт",
    "crm_files_company": "Файл CRM: компания",
    "crm_files_deal": "Файл CRM: сделка",
    "user": "Пользователь",
    "department": "Подразделение",
    "linked_company_contact": "Компания + Контакт",
    "linked_company_deal": "Компания + Сделка",
    "linked_contact_company": "Контакт + Компания",
    "linked_contact_deal": "Контакт + Сделка",
    "linked_deal_company": "Сделка + Компания",
    "linked_deal_contact": "Сделка + Контакт",
}


def build_report_timestamp(timestamp=None) -> str:
    value = timestamp or timezone.now()
    return timezone.localtime(value).strftime("%d.%m.%Y %H:%M:%S")


def _first_non_empty(*values) -> str:
    for value in values:
        normalized_value = _extract_display_value(value)
        if normalized_value:
            return normalized_value
    return ""


def _extract_display_value(value) -> str:
    if isinstance(value, list):
        for item in value:
            normalized_item = _extract_display_value(item)
            if normalized_item:
                return normalized_item
        return ""

    if isinstance(value, dict):
        for key in ("title", "TITLE", "name", "NAME", "VALUE", "value", "COMMENT", "SUBJECT", "FILE_NAME", "FILE_URL", "ID", "id"):
            normalized_item = _extract_display_value(value.get(key))
            if normalized_item:
                return normalized_item
        return ""

    return normalize_value(value)


def _build_person_title(row_payload: dict | None) -> str:
    fields = row_payload if isinstance(row_payload, dict) else {}
    parts = [
        normalize_value(fields.get("NAME")),
        normalize_value(fields.get("LAST_NAME")),
        normalize_value(fields.get("SECOND_NAME")),
    ]
    return " ".join(part for part in parts if part).strip()


def _build_linked_entity_title(entity_id: str, linked_records_map: dict, linked_payload_map: dict) -> str:
    if entity_id == "company":
        return _first_non_empty(
            linked_records_map.get("company", {}),
            (linked_payload_map.get("company") or {}).get("TITLE"),
        )

    if entity_id == "contact":
        return _first_non_empty(
            linked_records_map.get("contact", {}),
            _build_person_title(linked_payload_map.get("contact", {})),
            (linked_payload_map.get("contact") or {}).get("EMAIL"),
            (linked_payload_map.get("contact") or {}).get("PHONE"),
        )

    if entity_id == "deal":
        return _first_non_empty(
            linked_records_map.get("deal", {}),
            (linked_payload_map.get("deal") or {}).get("TITLE"),
        )

    return _first_non_empty(
        linked_records_map.get(entity_id, {}),
        (linked_payload_map.get(entity_id) or {}).get("TITLE"),
        (linked_payload_map.get(entity_id) or {}).get("NAME"),
    )


def _build_linked_title(entity_type: str, linked_records=None, linked_payload=None) -> str:
    linked_records_map = linked_records if isinstance(linked_records, dict) else {}
    linked_payload_map = linked_payload if isinstance(linked_payload, dict) else {}
    linked_schema = get_linked_import_schema(entity_type)
    entity_ids = [
        str(entity.get("id") or "").strip().lower()
        for entity in (linked_schema or {}).get("entities", [])
        if str(entity.get("id") or "").strip()
    ]
    if not entity_ids:
        entity_ids = ["company", "contact", "deal"]

    return " / ".join(
        part
        for part in [
            _build_linked_entity_title(entity_id, linked_records_map, linked_payload_map)
            for entity_id in entity_ids
        ]
        if part
    )


def build_report_entity_label(entity_type: str, *, entity_config: dict | None = None) -> str:
    if entity_type == SMART_PROCESS_ENTITY_TYPE:
        smart_process_title = normalize_value((entity_config or {}).get("title"))
        if smart_process_title:
            return f"Смарт-процесс: {smart_process_title}"
        return "Смарт-процесс"

    linked_schema = get_linked_import_schema(entity_type)
    if linked_schema is not None:
        linked_label = normalize_value(linked_schema.get("label"))
        if linked_label:
            return linked_label

    return REPORT_ENTITY_LABELS.get(str(entity_type or "").strip(), str(entity_type or "").strip())


def build_report_title(
    entity_type: str,
    *,
    row_payload: dict | None = None,
    linked_records: dict | None = None,
    linked_payload: dict | None = None,
) -> str:
    fields = row_payload if isinstance(row_payload, dict) else {}

    if get_linked_import_schema(entity_type) is not None:
        return _build_linked_title(entity_type, linked_records=linked_records, linked_payload=linked_payload)

    if entity_type in {"lead", "company", "deal", "task", "task_checklist_item", SMART_PROCESS_ENTITY_TYPE}:
        return _first_non_empty(fields.get("TITLE"))

    if entity_type in {"contact", "user"}:
        return _first_non_empty(
            _build_person_title(fields),
            fields.get("EMAIL"),
            fields.get("PHONE"),
        )

    if entity_type == "department":
        return _first_non_empty(fields.get("NAME"))

    if entity_type == "task_comment":
        return _first_non_empty(fields.get("POST_MESSAGE"))

    if entity_type in {"task_attachment", "crm_files_lead", "crm_files_contact", "crm_files_company", "crm_files_deal"}:
        return _first_non_empty(fields.get("FILE_NAME"), fields.get("FILE_URL"))

    if entity_type == "crm_activity":
        return _first_non_empty(fields.get("SUBJECT"))

    if entity_type == "crm_note":
        return _first_non_empty(fields.get("COMMENT"))

    return _first_non_empty(
        fields.get("TITLE"),
        _build_person_title(fields),
        fields.get("NAME"),
        fields.get("SUBJECT"),
        fields.get("COMMENT"),
        fields.get("POST_MESSAGE"),
        fields.get("FILE_NAME"),
        fields.get("EMAIL"),
        fields.get("PHONE"),
    )


def build_report_record_id(entity_type: str, record_id=None, *, linked_records: dict | None = None) -> str:
    linked_records_map = linked_records if isinstance(linked_records, dict) else {}
    if linked_records_map:
        linked_schema = get_linked_import_schema(entity_type)
        entity_ids = [
            str(entity.get("id") or "").strip().lower()
            for entity in (linked_schema or {}).get("entities", [])
            if str(entity.get("id") or "").strip()
        ]
        if not entity_ids:
            entity_ids = list(linked_records_map.keys())

        entity_labels = {
            "company": "Компания",
            "contact": "Контакт",
            "deal": "Сделка",
        }
        labels = []
        for entity_id in entity_ids:
            entity_record_id = normalize_value((linked_records_map.get(entity_id) or {}).get("id"))
            if not entity_record_id:
                continue
            labels.append(f"{entity_labels.get(entity_id, entity_id)} {entity_record_id}")
        if labels:
            return " · ".join(labels)

    return normalize_value(record_id)


def build_import_result_report_meta(
    entity_type: str,
    *,
    row_payload: dict | None = None,
    record_id=None,
    linked_records: dict | None = None,
    linked_payload: dict | None = None,
    entity_config: dict | None = None,
    timestamp=None,
) -> dict:
    return {
        "report_date_time": build_report_timestamp(timestamp),
        "report_entity": build_report_entity_label(entity_type, entity_config=entity_config),
        "report_title": build_report_title(
            entity_type,
            row_payload=row_payload,
            linked_records=linked_records,
            linked_payload=linked_payload,
        ),
        "report_record_id": build_report_record_id(entity_type, record_id, linked_records=linked_records),
    }
