from typing import Any
from b24pysdk.bitrix_api.requests import BitrixAPIRequest


TASK_FIELDS = [
    {
        "id": "TITLE",
        "title": "Название задачи",
        "type": "string",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "DESCRIPTION",
        "title": "Описание",
        "type": "text",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "RESPONSIBLE_ID",
        "title": "Ответственный (ID)",
        "type": "integer",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "ACCOMPLICES",
        "title": "Соисполнители (ID)",
        "type": "integer",
        "required": False,
        "multiple": True,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "AUDITORS",
        "title": "Наблюдатели (ID)",
        "type": "integer",
        "required": False,
        "multiple": True,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "CREATED_BY",
        "title": "Постановщик (ID)",
        "type": "integer",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "GROUP_ID",
        "title": "Рабочая группа (ID)",
        "type": "integer",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "PRIORITY",
        "title": "Приоритет",
        "type": "integer",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "TAGS",
        "title": "Теги",
        "type": "string",
        "required": False,
        "multiple": True,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "DEADLINE",
        "title": "Крайний срок",
        "type": "datetime",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "START_DATE_PLAN",
        "title": "Плановая дата начала",
        "type": "datetime",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "END_DATE_PLAN",
        "title": "Плановая дата завершения",
        "type": "datetime",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "XML_ID",
        "title": "Внешний ID",
        "type": "string",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "PARENT_ID",
        "title": "ID родительской задачи",
        "type": "integer",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
]


TASK_COMMENT_FIELDS = [
    {
        "id": "TASK_ID",
        "title": "ID задачи",
        "type": "string",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "AUTHOR_ID",
        "title": "Пользователь",
        "type": "integer",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "POST_MESSAGE",
        "title": "Комментарий",
        "type": "text",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
]


TASK_CHECKLIST_ITEM_FIELDS = [
    {
        "id": "TASK_ID",
        "title": "ID задачи",
        "type": "string",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "TITLE",
        "title": "Пункт чек-листа",
        "type": "string",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "IS_COMPLETE",
        "title": "Выполнено",
        "type": "boolean",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
]


TASK_ATTACHMENT_FIELDS = [
    {
        "id": "TASK_ID",
        "title": "ID задачи",
        "type": "string",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "FILE_URL",
        "title": "Ссылка на файл",
        "type": "string",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "FILE_NAME",
        "title": "Имя файла",
        "type": "string",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
]


USER_FIELDS = [
    {
        "id": "NAME",
        "title": "Имя",
        "type": "string",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "LAST_NAME",
        "title": "Фамилия",
        "type": "string",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "SECOND_NAME",
        "title": "Отчество",
        "type": "string",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "EMAIL",
        "title": "Email",
        "type": "string",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "PERSONAL_PHONE",
        "title": "Личный телефон",
        "type": "string",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "PERSONAL_MOBILE",
        "title": "Мобильный телефон",
        "type": "string",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "WORK_PHONE",
        "title": "Рабочий телефон",
        "type": "string",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "WORK_POSITION",
        "title": "Должность",
        "type": "string",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "UF_DEPARTMENT",
        "title": "Отдел (ID)",
        "type": "integer",
        "required": False,
        "multiple": True,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "ACTIVE",
        "title": "Активен",
        "type": "boolean",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "XML_ID",
        "title": "Внешний ID",
        "type": "string",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
]


DEPARTMENT_FIELDS = [
    {
        "id": "NAME",
        "title": "Название отдела",
        "type": "string",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "PARENT",
        "title": "ID родительского отдела",
        "type": "integer",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "UF_HEAD",
        "title": "Руководитель (ID)",
        "type": "integer",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "SORT",
        "title": "Сортировка",
        "type": "integer",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "XML_ID",
        "title": "Внешний ID",
        "type": "string",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
]


CRM_FILES_FIELDS = [
    {
        "id": "ID",
        "title": "ID записи",
        "type": "integer",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "FILE_URL",
        "title": "Ссылка на файл",
        "type": "string",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "FILE_NAME",
        "title": "Имя файла",
        "type": "string",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "FIELD_ID",
        "title": "ID поля в Bitrix24",
        "type": "string",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
]


CRM_ACTIVITY_FIELDS = [
    {
        "id": "OWNER_TYPE_ID",
        "title": "Тип сущности CRM",
        "type": "string",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [
            {"id": "1", "title": "Лид"},
            {"id": "2", "title": "Сделка"},
            {"id": "3", "title": "Контакт"},
            {"id": "4", "title": "Компания"},
        ],
    },
    {
        "id": "OWNER_ID",
        "title": "ID записи CRM",
        "type": "integer",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "TYPE_ID",
        "title": "Тип активности",
        "type": "string",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [
            {"id": "1", "title": "Встреча"},
            {"id": "2", "title": "Звонок"},
            {"id": "4", "title": "Email"},
            {"id": "6", "title": "Задание"},
        ],
    },
    {
        "id": "SUBJECT",
        "title": "Тема / заголовок",
        "type": "string",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "DESCRIPTION",
        "title": "Описание",
        "type": "text",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "START_TIME",
        "title": "Дата начала",
        "type": "datetime",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "END_TIME",
        "title": "Дата окончания",
        "type": "datetime",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "DEADLINE",
        "title": "Крайний срок",
        "type": "datetime",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "RESPONSIBLE_ID",
        "title": "Ответственный (ID)",
        "type": "integer",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "DIRECTION",
        "title": "Направление",
        "type": "string",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [
            {"id": "1", "title": "Входящее"},
            {"id": "2", "title": "Исходящее"},
        ],
    },
    {
        "id": "STATUS",
        "title": "Статус",
        "type": "string",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [
            {"id": "0", "title": "Новая"},
            {"id": "1", "title": "В работе"},
            {"id": "2", "title": "Ожидание"},
            {"id": "3", "title": "Завершена"},
        ],
    },
    {
        "id": "PRIORITY",
        "title": "Приоритет",
        "type": "string",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [
            {"id": "1", "title": "Низкий"},
            {"id": "2", "title": "Средний"},
            {"id": "3", "title": "Высокий"},
        ],
    },
    {
        "id": "COMMUNICATIONS_VALUE",
        "title": "Телефон / Email (для звонков и писем)",
        "type": "string",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
]

CRM_NOTE_FIELDS = [
    {
        "id": "ENTITY_TYPE",
        "title": "Тип сущности CRM",
        "type": "string",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [
            {"id": "lead", "title": "Лид"},
            {"id": "contact", "title": "Контакт"},
            {"id": "company", "title": "Компания"},
            {"id": "deal", "title": "Сделка"},
        ],
    },
    {
        "id": "ENTITY_ID",
        "title": "ID записи CRM",
        "type": "integer",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "COMMENT",
        "title": "Текст заметки",
        "type": "text",
        "required": True,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
    {
        "id": "CREATED_TIME",
        "title": "Дата создания",
        "type": "datetime",
        "required": False,
        "multiple": False,
        "is_custom": False,
        "items": [],
    },
]


STATIC_FIELD_CATALOGS = {
    "task": TASK_FIELDS,
    "task_comment": TASK_COMMENT_FIELDS,
    "task_checklist_item": TASK_CHECKLIST_ITEM_FIELDS,
    "task_attachment": TASK_ATTACHMENT_FIELDS,
    "crm_files_lead": CRM_FILES_FIELDS,
    "crm_files_contact": CRM_FILES_FIELDS,
    "crm_files_company": CRM_FILES_FIELDS,
    "crm_files_deal": CRM_FILES_FIELDS,
    "user": USER_FIELDS,
    "department": DEPARTMENT_FIELDS,
    "crm_activity": CRM_ACTIVITY_FIELDS,
    "crm_note": CRM_NOTE_FIELDS,
}
SMART_PROCESS_ENTITY_TYPE = "smart_process"

CONTACT_OPTIONAL_NAME_FIELDS = {"NAME", "LAST_NAME", "SECOND_NAME"}
LINKED_COMPANY_CONTACT_ENTITY_TYPE = "linked_company_contact"
LINKED_ENTITY_PREFIXES = {
    "company": "COMPANY__",
    "contact": "CONTACT__",
}
LINKED_ENTITY_LABELS = {
    "company": "Компания",
    "contact": "Контакт",
}
LINKED_EXCLUDED_SOURCE_IDS = {
    "contact": {"COMPANY_ID"},
}


def normalize_bitrix_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    return str(value or "").strip().lower() in {"1", "true", "y", "yes"}


def normalize_field_items(items: Any) -> list[dict]:
    if isinstance(items, dict):
        return [
            {
                "id": str(item_id),
                "title": str(item_title),
            }
            for item_id, item_title in items.items()
        ]

    if isinstance(items, list):
        normalized_items = []
        for item in items:
            if isinstance(item, dict):
                normalized_items.append(
                    {
                        "id": str(item.get("ID", item.get("id", ""))),
                        "title": str(item.get("VALUE", item.get("value", item.get("title", "")))),
                    }
                )
        return normalized_items

    return []


def normalize_fields_result(fields_result: dict[str, Any], entity_type: str = "") -> list[dict]:
    normalized_fields = []
    for field_id, meta in fields_result.items():
        field_meta = meta if isinstance(meta, dict) else {}
        if entity_type == SMART_PROCESS_ENTITY_TYPE and (
            normalize_bitrix_bool(field_meta.get("isReadOnly"))
            or normalize_bitrix_bool(field_meta.get("isImmutable"))
        ):
            continue

        is_required = normalize_bitrix_bool(field_meta.get("isRequired", field_meta.get("required")))
        if entity_type == "contact" and field_id in CONTACT_OPTIONAL_NAME_FIELDS:
            is_required = False

        upper_name = str(field_meta.get("upperName") or "")
        is_custom = (
            field_id.startswith("UF_CRM_")
            or upper_name.startswith("UF_CRM_")
            or field_id.startswith("ufCrm")
        )
        normalized_fields.append(
            {
                "id": field_id,
                "title": str(field_meta.get("title") or field_meta.get("formLabel") or field_id),
                "type": str(field_meta.get("type") or field_meta.get("TYPE") or "string"),
                "required": is_required,
                "multiple": normalize_bitrix_bool(field_meta.get("isMultiple", field_meta.get("multiple"))),
                "is_custom": is_custom,
                "items": normalize_field_items(field_meta.get("items")),
            }
        )

    return sorted(normalized_fields, key=lambda item: (item["is_custom"], item["title"], item["id"]))


def unwrap_bitrix_result(response):
    return getattr(response, "result", response)


def unwrap_smart_process_fields_result(result):
    if not isinstance(result, dict):
        return result

    wrapped_fields = result.get("fields")
    if isinstance(wrapped_fields, dict):
        return wrapped_fields

    wrapped_result = result.get("result")
    if isinstance(wrapped_result, dict) and isinstance(wrapped_result.get("fields"), dict):
        return wrapped_result["fields"]

    return result


def normalize_smart_process_entity_config(entity_config: Any) -> dict:
    config = entity_config if isinstance(entity_config, dict) else {}

    raw_entity_type_id = (
        config.get("entityTypeId")
        or config.get("entity_type_id")
        or config.get("smart_process_entity_type_id")
    )
    try:
        entity_type_id = int(raw_entity_type_id)
    except (TypeError, ValueError):
        entity_type_id = 0

    if entity_type_id <= 0:
        raise ValueError("entity_type_id is required for smart_process")

    normalized_config = {
        "entityTypeId": entity_type_id,
    }
    title = str(config.get("title") or config.get("entity_title") or "").strip()
    if title:
        normalized_config["title"] = title
    return normalized_config


def fetch_smart_process_types(account) -> list[dict]:
    response = BitrixAPIRequest(
        bitrix_token=account,
        api_method="crm.type.list",
        params={},
    )
    result = unwrap_bitrix_result(response)
    if isinstance(result, dict):
        items = result.get("types") or result.get("items") or result.get("result") or []
    else:
        items = result

    normalized_items = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        raw_entity_type_id = item.get("entityTypeId") or item.get("entity_type_id") or item.get("id")
        try:
            entity_type_id = int(raw_entity_type_id)
        except (TypeError, ValueError):
            continue
        if entity_type_id <= 0:
            continue
        normalized_items.append(
            {
                "entityTypeId": entity_type_id,
                "title": str(item.get("title") or item.get("name") or f"Smart Process {entity_type_id}"),
                "isCategoriesEnabled": normalize_bitrix_bool(item.get("isCategoriesEnabled")),
                "isStagesEnabled": normalize_bitrix_bool(item.get("isStagesEnabled")),
                "isClientEnabled": normalize_bitrix_bool(item.get("isClientEnabled")),
            }
        )

    return sorted(normalized_items, key=lambda item: (item["title"].lower(), item["entityTypeId"]))


def _normalize_bitrix_named_items(items: Any, id_keys: tuple[str, ...], title_keys: tuple[str, ...]) -> list[dict]:
    normalized_items = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue

        item_id = ""
        for id_key in id_keys:
            raw_id = item.get(id_key)
            if raw_id not in (None, ""):
                item_id = str(raw_id)
                break

        item_title = ""
        for title_key in title_keys:
            raw_title = item.get(title_key)
            if raw_title not in (None, ""):
                item_title = str(raw_title)
                break

        if not item_id or not item_title:
            continue

        normalized_items.append({"id": item_id, "title": item_title})

    return normalized_items


def fetch_smart_process_categories(account, entity_type_id: int) -> list[dict]:
    response = BitrixAPIRequest(
        bitrix_token=account,
        api_method="crm.category.list",
        params={"entityTypeId": entity_type_id},
    )
    result = unwrap_bitrix_result(response)
    if isinstance(result, dict):
        items = result.get("categories") or result.get("items") or result.get("result") or []
    else:
        items = result

    return _normalize_bitrix_named_items(items, ("ID", "id"), ("NAME", "name", "title"))


def fetch_smart_process_stages(account, entity_type_id: int, categories: list[dict] | None = None) -> list[dict]:
    category_items = categories if isinstance(categories, list) else fetch_smart_process_categories(account, entity_type_id)
    category_ids = []

    for item in category_items:
        if not isinstance(item, dict):
            continue
        category_id = str(item.get("id") or "").strip()
        if category_id:
            category_ids.append(category_id)

    if not category_ids:
        category_ids = ["0"]

    normalized_items = []
    seen_ids = set()

    for category_id in category_ids:
        entity_ids = [f"DYNAMIC_{entity_type_id}_STAGE_{category_id}"]
        if category_id == "0":
            entity_ids.append(f"DYNAMIC_{entity_type_id}_STAGE")

        found_items_for_category = False

        for entity_id in entity_ids:
            response = BitrixAPIRequest(
                bitrix_token=account,
                api_method="crm.status.list",
                params={"filter": {"ENTITY_ID": entity_id}},
            )
            result = unwrap_bitrix_result(response)
            if isinstance(result, dict):
                items = result.get("statuses") or result.get("items") or result.get("result") or []
            else:
                items = result

            normalized_stage_items = _normalize_bitrix_named_items(items, ("STATUS_ID", "ID", "id"), ("NAME", "name", "title"))
            if normalized_stage_items:
                found_items_for_category = True

            for item in normalized_stage_items:
                item_id = str(item.get("id") or "").strip()
                if not item_id or item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
                normalized_items.append(item)

            if found_items_for_category:
                break

    return normalized_items


def enrich_smart_process_fields(account, entity_type_id: int, fields: list[dict]) -> list[dict]:
    categories = None
    stages = None
    enriched_fields = []

    for field in fields:
        field_id = str(field.get("id") or "")
        normalized_field_id = field_id.lower()
        field_items = field.get("items") if isinstance(field.get("items"), list) else []

        if field_items:
            enriched_fields.append(field)
            continue

        if normalized_field_id == "categoryid":
            if categories is None:
                categories = fetch_smart_process_categories(account, entity_type_id)
            enriched_fields.append({**field, "items": categories})
            continue

        if normalized_field_id == "stageid":
            if stages is None:
                stages = fetch_smart_process_stages(account, entity_type_id, categories=categories)
            enriched_fields.append({**field, "items": stages})
            continue

        enriched_fields.append(field)

    return enriched_fields


def fetch_entity_fields(account, entity_type: str, entity_config: dict | None = None) -> list[dict]:
    static_catalog = STATIC_FIELD_CATALOGS.get(entity_type)
    if static_catalog is not None:
        return [dict(field) for field in static_catalog]

    entity_fields_loaders = {
        "lead": lambda client: client.crm.lead.fields().result,
        "contact": lambda client: client.crm.contact.fields().result,
        "company": lambda client: client.crm.company.fields().result,
        "deal": lambda client: client.crm.deal.fields().result,
    }

    if entity_type == LINKED_COMPANY_CONTACT_ENTITY_TYPE:
        company_fields_result = entity_fields_loaders["company"](account.client)
        contact_fields_result = entity_fields_loaders["contact"](account.client)
        if not isinstance(company_fields_result, dict) or not isinstance(contact_fields_result, dict):
            raise ValueError("Unable to load entity fields")

        linked_fields = []
        for linked_entity, source_entity_type, source_fields_result in (
            ("company", "company", company_fields_result),
            ("contact", "contact", contact_fields_result),
        ):
            source_fields = normalize_fields_result(source_fields_result, entity_type=source_entity_type)
            prefix = LINKED_ENTITY_PREFIXES[linked_entity]
            entity_label = LINKED_ENTITY_LABELS[linked_entity]
            excluded_source_ids = LINKED_EXCLUDED_SOURCE_IDS.get(linked_entity, set())
            for source_field in source_fields:
                source_field_id = str(source_field.get("id") or "")
                if not source_field_id or source_field_id in excluded_source_ids:
                    continue

                linked_fields.append(
                    {
                        **source_field,
                        "id": f"{prefix}{source_field_id}",
                        "title": f"{entity_label} / {source_field['title']}",
                        "linked_entity": linked_entity,
                        "linked_source_id": source_field_id,
                    }
                )

        return sorted(
            linked_fields,
            key=lambda item: (
                0 if item.get("linked_entity") == "company" else 1,
                item.get("is_custom", False),
                item.get("title", ""),
                item.get("id", ""),
            ),
        )

    if entity_type == SMART_PROCESS_ENTITY_TYPE:
        smart_process_config = normalize_smart_process_entity_config(entity_config)
        response = BitrixAPIRequest(
            bitrix_token=account,
            api_method="crm.item.fields",
            params={"entityTypeId": smart_process_config["entityTypeId"]},
        )
        fields_result = unwrap_smart_process_fields_result(unwrap_bitrix_result(response))
        if not isinstance(fields_result, dict):
            raise ValueError("Unable to load entity fields")
        normalized_fields = normalize_fields_result(fields_result, entity_type=entity_type)
        return enrich_smart_process_fields(account, smart_process_config["entityTypeId"], normalized_fields)

    loader = entity_fields_loaders.get(entity_type)
    if loader is None:
        raise ValueError("Unsupported entity type")

    fields_result = loader(account.client)
    if not isinstance(fields_result, dict):
        raise ValueError("Unable to load entity fields")

    return normalize_fields_result(fields_result, entity_type=entity_type)
