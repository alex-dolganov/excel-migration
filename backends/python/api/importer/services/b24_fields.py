from typing import Any
from b24pysdk.bitrix_api.requests import BitrixAPIRequest

from .task_resolution import invoke_with_fallbacks


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
TASK_SYSTEM_FIELD_IDS = {
    str(field.get("id") or "").strip()
    for field in TASK_FIELDS
    if str(field.get("id") or "").strip()
}


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
TASK_USERFIELD_TYPE_MAP = {
    "string": "string",
    "double": "double",
    "integer": "integer",
    "datetime": "datetime",
    "date": "date",
    "boolean": "boolean",
    "enumeration": "enumeration",
    "file": "file",
    "disk_file": "file",
    "employee": "integer",
    "crm": "string",
    "url": "string",
}

CONTACT_OPTIONAL_NAME_FIELDS = {"NAME", "LAST_NAME", "SECOND_NAME"}
LINKED_COMPANY_CONTACT_ENTITY_TYPE = "linked_company_contact"
LINKED_COMPANY_DEAL_ENTITY_TYPE = "linked_company_deal"
LINKED_IMPORT_SCHEMAS = {
    LINKED_COMPANY_CONTACT_ENTITY_TYPE: {
        "label": "Компания + Контакт",
        "entities": [
            {
                "id": "company",
                "label": "Компания",
                "source_entity_type": "company",
                "prefix": "COMPANY__",
                "excluded_source_ids": (),
            },
            {
                "id": "contact",
                "label": "Контакт",
                "source_entity_type": "contact",
                "prefix": "CONTACT__",
                "excluded_source_ids": ("COMPANY_ID",),
            },
        ],
    },
    LINKED_COMPANY_DEAL_ENTITY_TYPE: {
        "label": "Компания + Сделка",
        "entities": [
            {
                "id": "company",
                "label": "Компания",
                "source_entity_type": "company",
                "prefix": "COMPANY__",
                "excluded_source_ids": (),
            },
            {
                "id": "deal",
                "label": "Сделка",
                "source_entity_type": "deal",
                "prefix": "DEAL__",
                "excluded_source_ids": ("COMPANY_ID",),
            },
        ],
    },
}
STANDARD_CRM_STATUS_ENTITY_IDS = {
    "lead": {
        "SOURCE_ID": ("SOURCE",),
        "HONORIFIC": ("HONORIFIC",),
        "STATUS_ID": ("STATUS",),
    },
    "contact": {
        "SOURCE_ID": ("SOURCE",),
        "HONORIFIC": ("HONORIFIC",),
        "TYPE_ID": ("CONTACT_TYPE",),
    },
    "company": {
        "EMPLOYEES": ("EMPLOYEES",),
        "INDUSTRY": ("INDUSTRY",),
        "COMPANY_TYPE": ("COMPANY_TYPE",),
    },
    "deal": {
        "SOURCE_ID": ("SOURCE",),
        "TYPE_ID": ("DEAL_TYPE",),
        "STAGE_ID": ("DEAL_STAGE",),
    },
}
STANDARD_CRM_FRIENDLY_FIELD_TITLES = {
    "UTM_SOURCE": "Сквозная аналитика: источник",
    "UTM_MEDIUM": "Сквозная аналитика: тип трафика",
    "UTM_CAMPAIGN": "Сквозная аналитика: кампания",
    "UTM_CONTENT": "Сквозная аналитика: содержание",
    "UTM_TERM": "Сквозная аналитика: ключевая фраза",
}


def normalize_bitrix_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    return str(value or "").strip().lower() in {"1", "true", "y", "yes"}


def normalize_field_items(items: Any) -> list[dict]:
    if isinstance(items, dict):
        normalized_items = []
        for item_id, item_meta in items.items():
            if isinstance(item_meta, dict):
                nested_item_id = item_meta.get("ID", item_meta.get("id", item_id))
                nested_item_title = item_meta.get(
                    "VALUE",
                    item_meta.get("value", item_meta.get("title", item_meta.get("NAME", item_meta.get("name", "")))),
                )
                normalized_items.append(
                    {
                        "id": str(nested_item_id),
                        "title": str(nested_item_title),
                    }
                )
                continue

            normalized_items.append(
                {
                    "id": str(item_id),
                    "title": str(item_meta),
                }
            )
        return normalized_items

    if isinstance(items, list):
        normalized_items = []
        for item in items:
            if isinstance(item, dict):
                normalized_items.append(
                    {
                        "id": str(item.get("ID", item.get("id", ""))),
                        "title": str(item.get("VALUE", item.get("value", item.get("title", item.get("NAME", item.get("name", "")))))),
                    }
                )
        return normalized_items

    return []


def _extract_field_label_value(value: Any) -> str:
    if value in (None, ""):
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        for key in ("ru", "RU", "ru_RU", "ru-RU", "value", "VALUE", "label", "LABEL", "title", "TITLE", "name", "NAME"):
            nested_value = value.get(key)
            if nested_value in (None, ""):
                continue
            normalized_value = str(nested_value).strip()
            if normalized_value:
                return normalized_value

        for nested_value in value.values():
            if nested_value in (None, ""):
                continue
            normalized_value = str(nested_value).strip()
            if normalized_value:
                return normalized_value

        return ""

    return str(value).strip()


def _resolve_bitrix_field_title(field_id: str, field_meta: dict[str, Any]) -> str:
    normalized_field_id = str(field_id or "").strip()
    normalized_upper_name = str(field_meta.get("upperName") or "").strip().upper()
    machine_names = {
        normalized_field_id.upper(),
        normalized_upper_name,
    }
    label_keys = (
        "title",
        "formLabel",
        "editFormLabel",
        "listColumnLabel",
        "filterLabel",
        "label",
        "name",
        "form_label",
        "edit_form_label",
        "list_column_label",
        "filter_label",
        "EDIT_FORM_LABEL",
        "LIST_COLUMN_LABEL",
        "FILTER_LABEL",
        "LABEL",
        "NAME",
    )

    fallback_title = ""
    for key in label_keys:
        label_value = _extract_field_label_value(field_meta.get(key))
        if not label_value:
            continue

        if not fallback_title:
            fallback_title = label_value

        if label_value.upper() not in machine_names:
            return label_value

    friendly_title = STANDARD_CRM_FRIENDLY_FIELD_TITLES.get(normalized_field_id.upper()) or STANDARD_CRM_FRIENDLY_FIELD_TITLES.get(normalized_upper_name)
    resolved_title = fallback_title or normalized_field_id
    if friendly_title and resolved_title.upper() in machine_names:
        return friendly_title

    return resolved_title


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
            or (entity_type == "task" and str(field_id or "").upper().startswith("UF_"))
        )
        normalized_fields.append(
            {
                "id": field_id,
                "title": _resolve_bitrix_field_title(field_id, field_meta),
                "type": str(field_meta.get("type") or field_meta.get("TYPE") or "string"),
                "required": is_required,
                "multiple": normalize_bitrix_bool(field_meta.get("isMultiple", field_meta.get("multiple"))),
                "is_custom": is_custom,
                "items": normalize_field_items(field_meta.get("items")),
            }
        )

    return sorted(normalized_fields, key=lambda item: (item["is_custom"], item["title"], item["id"]))


def extract_smart_process_status_entity_ids(fields_result: dict[str, Any]) -> dict[str, str]:
    if not isinstance(fields_result, dict):
        return {}

    status_entity_ids_by_field = {}

    for field_id, meta in fields_result.items():
        field_meta = meta if isinstance(meta, dict) else {}
        field_type = str(field_meta.get("type") or field_meta.get("TYPE") or "").strip().lower()
        if field_type != "crm_status":
            continue

        settings = field_meta.get("settings") if isinstance(field_meta.get("settings"), dict) else {}
        status_entity_id = str(
            field_meta.get("statusType")
            or field_meta.get("status_type")
            or settings.get("statusType")
            or settings.get("status_type")
            or ""
        ).strip()
        if not status_entity_id:
            continue

        status_entity_ids_by_field[str(field_id).strip().lower()] = status_entity_id

    return status_entity_ids_by_field


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


def unwrap_task_fields_result(result):
    if not isinstance(result, dict):
        return result

    wrapped_fields = result.get("fields")
    if isinstance(wrapped_fields, dict):
        return wrapped_fields

    wrapped_result = result.get("result")
    if isinstance(wrapped_result, dict) and isinstance(wrapped_result.get("fields"), dict):
        return wrapped_result["fields"]

    return result


def extract_task_userfield_items(result) -> list[dict]:
    if isinstance(result, dict):
        for key in ("items", "result", "userFields", "user_fields"):
            items = result.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        return []

    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]

    return []


def normalize_task_userfield_result(task_userfield_meta: dict[str, Any]) -> dict | None:
    if not isinstance(task_userfield_meta, dict):
        return None

    field_id = str(
        task_userfield_meta.get("FIELD_NAME")
        or task_userfield_meta.get("fieldName")
        or task_userfield_meta.get("field_name")
        or ""
    ).strip()
    if not field_id:
        return None

    settings = task_userfield_meta.get("SETTINGS") if isinstance(task_userfield_meta.get("SETTINGS"), dict) else {}
    user_type_id = str(
        task_userfield_meta.get("USER_TYPE_ID")
        or task_userfield_meta.get("userTypeId")
        or task_userfield_meta.get("user_type_id")
        or task_userfield_meta.get("type")
        or "string"
    ).strip().lower()
    normalized_type = TASK_USERFIELD_TYPE_MAP.get(user_type_id, user_type_id or "string")
    normalized_fields = normalize_fields_result(
        {
            field_id: {
                "title": task_userfield_meta.get("EDIT_FORM_LABEL")
                or task_userfield_meta.get("editFormLabel")
                or task_userfield_meta.get("LIST_COLUMN_LABEL")
                or task_userfield_meta.get("listColumnLabel")
                or task_userfield_meta.get("LIST_FILTER_LABEL")
                or task_userfield_meta.get("listFilterLabel")
                or task_userfield_meta.get("LABEL")
                or task_userfield_meta.get("label")
                or task_userfield_meta.get("FIELD_NAME")
                or task_userfield_meta.get("fieldName")
                or field_id,
                "formLabel": task_userfield_meta.get("EDIT_FORM_LABEL")
                or task_userfield_meta.get("editFormLabel")
                or task_userfield_meta.get("LABEL")
                or task_userfield_meta.get("label"),
                "editFormLabel": task_userfield_meta.get("EDIT_FORM_LABEL")
                or task_userfield_meta.get("editFormLabel"),
                "listColumnLabel": task_userfield_meta.get("LIST_COLUMN_LABEL")
                or task_userfield_meta.get("listColumnLabel"),
                "filterLabel": task_userfield_meta.get("LIST_FILTER_LABEL")
                or task_userfield_meta.get("listFilterLabel"),
                "type": normalized_type,
                "isRequired": task_userfield_meta.get("MANDATORY", task_userfield_meta.get("mandatory")),
                "isMultiple": task_userfield_meta.get("MULTIPLE", task_userfield_meta.get("multiple")),
                "items": task_userfield_meta.get("LIST")
                or settings.get("LIST")
                or task_userfield_meta.get("items")
                or settings.get("items")
                or [],
            }
        },
        entity_type="task",
    )
    return normalized_fields[0] if normalized_fields else None


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


def get_linked_import_schema(entity_type: str) -> dict | None:
    schema = LINKED_IMPORT_SCHEMAS.get(str(entity_type or "").strip())
    if not isinstance(schema, dict):
        return None

    normalized_entities = []
    for entity in schema.get("entities") if isinstance(schema.get("entities"), list) else []:
        if not isinstance(entity, dict):
            continue

        entity_id = str(entity.get("id") or "").strip().lower()
        source_entity_type = str(entity.get("source_entity_type") or "").strip()
        prefix = str(entity.get("prefix") or "").strip()
        if not entity_id or not source_entity_type or not prefix:
            continue

        excluded_source_ids = []
        seen_source_ids = set()
        for source_id in entity.get("excluded_source_ids") if isinstance(entity.get("excluded_source_ids"), (list, tuple, set)) else []:
            normalized_source_id = str(source_id or "").strip()
            if not normalized_source_id or normalized_source_id in seen_source_ids:
                continue
            seen_source_ids.add(normalized_source_id)
            excluded_source_ids.append(normalized_source_id)

        normalized_entities.append(
            {
                "id": entity_id,
                "label": str(entity.get("label") or entity_id),
                "source_entity_type": source_entity_type,
                "prefix": prefix,
                "excluded_source_ids": excluded_source_ids,
            }
        )

    if not normalized_entities:
        return None

    return {
        "entity_type": str(entity_type or "").strip(),
        "label": str(schema.get("label") or entity_type or "").strip(),
        "entities": normalized_entities,
    }


def build_linked_entities_payload(entity_type: str) -> list[dict]:
    schema = get_linked_import_schema(entity_type)
    if schema is None:
        return []

    return [dict(entity) for entity in schema["entities"]]


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


def fetch_standard_crm_status_items(account, entity_ids: tuple[str, ...]) -> list[dict]:
    normalized_items = []
    seen_ids = set()

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

        normalized_status_items = _normalize_bitrix_named_items(items, ("STATUS_ID", "ID", "id"), ("NAME", "name", "title"))
        for item in normalized_status_items:
            item_id = str(item.get("id") or "").strip()
            if not item_id or item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            normalized_items.append(item)

        if normalized_items:
            break

    return normalized_items


def fetch_standard_crm_categories(account, entity_type_id: int) -> list[dict]:
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


def fetch_crm_currency_items(account) -> list[dict]:
    response = BitrixAPIRequest(
        bitrix_token=account,
        api_method="crm.currency.list",
        params={},
    )
    result = unwrap_bitrix_result(response)
    if isinstance(result, dict):
        items = result.get("currencies") or result.get("items") or result.get("result") or []
    else:
        items = result

    return _normalize_bitrix_named_items(
        items,
        ("CURRENCY", "currency", "ID", "id"),
        ("FULL_NAME", "full_name", "NAME", "name", "title"),
    )


def enrich_standard_crm_status_fields(account, entity_type: str, fields: list[dict]) -> list[dict]:
    status_entity_ids_by_field = STANDARD_CRM_STATUS_ENTITY_IDS.get(str(entity_type or "").strip(), {})
    category_entity_type_id = 2 if str(entity_type or "").strip() == "deal" else 0
    if not status_entity_ids_by_field:
        status_entity_ids_by_field = {}

    cached_items: dict[tuple[str, ...], list[dict]] = {}
    category_items: list[dict] | None = None
    currency_items: list[dict] | None = None
    enriched_fields = []

    for field in fields:
        field_items = field.get("items") if isinstance(field.get("items"), list) else []
        field_type = str(field.get("type") or "").strip().lower()
        field_id = str(field.get("id") or "").strip().upper()
        status_entity_ids = status_entity_ids_by_field.get(field_id)

        if field_items:
            enriched_fields.append(field)
            continue

        if field_id == "CATEGORY_ID" and category_entity_type_id > 0:
            if category_items is None:
                category_items = fetch_standard_crm_categories(account, category_entity_type_id)
            enriched_fields.append({**field, "items": category_items})
            continue

        if field_id == "CURRENCY_ID":
            if currency_items is None:
                currency_items = fetch_crm_currency_items(account)
            enriched_fields.append({**field, "items": currency_items})
            continue

        if field_type != "crm_status" or not status_entity_ids:
            enriched_fields.append(field)
            continue

        if status_entity_ids not in cached_items:
            cached_items[status_entity_ids] = fetch_standard_crm_status_items(account, status_entity_ids)

        enriched_fields.append({**field, "items": cached_items[status_entity_ids]})

    return enriched_fields


def enrich_smart_process_fields(
    account,
    entity_type_id: int,
    fields: list[dict],
    *,
    status_entity_ids_by_field: dict[str, str] | None = None,
) -> list[dict]:
    categories = None
    stages = None
    cached_status_items: dict[str, list[dict]] = {}
    enriched_fields = []
    smart_status_entity_ids = status_entity_ids_by_field if isinstance(status_entity_ids_by_field, dict) else {}

    for field in fields:
        field_id = str(field.get("id") or "")
        normalized_field_id = field_id.lower()
        field_items = field.get("items") if isinstance(field.get("items"), list) else []
        field_type = str(field.get("type") or "").strip().lower()

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

        status_entity_id = smart_status_entity_ids.get(normalized_field_id, "")
        if field_type == "crm_status" and status_entity_id:
            if status_entity_id not in cached_status_items:
                cached_status_items[status_entity_id] = fetch_standard_crm_status_items(account, (status_entity_id,))
            enriched_fields.append({**field, "items": cached_status_items[status_entity_id]})
            continue

        enriched_fields.append(field)

    return enriched_fields


def fetch_entity_fields(account, entity_type: str, entity_config: dict | None = None) -> list[dict]:
    if entity_type == "task":
        task_fields_result = None
        task_client = getattr(getattr(account, "client", None), "tasks", None)
        task_scope = getattr(task_client, "task", None) or getattr(task_client, "tasks", None)

        task_field_loaders = []
        if task_scope is not None:
            get_fields = getattr(task_scope, "getFields", None)
            if callable(get_fields):
                task_field_loaders.append(lambda: get_fields())

            get_fields_lower = getattr(task_scope, "getfields", None)
            if callable(get_fields_lower):
                task_field_loaders.append(lambda: get_fields_lower())

        task_field_loaders.append(
            lambda: BitrixAPIRequest(
                bitrix_token=account,
                api_method="tasks.task.getFields",
                params={},
            )
        )

        try:
            task_fields_result = unwrap_bitrix_result(invoke_with_fallbacks(task_field_loaders))
        except Exception:
            task_fields_result = None

        task_fields_payload = unwrap_task_fields_result(task_fields_result)
        normalized_task_fields = normalize_fields_result(task_fields_payload, entity_type=entity_type) if isinstance(task_fields_payload, dict) else []
        normalized_task_fields = [
            field
            for field in normalized_task_fields
            if str(field.get("id") or "").strip() in TASK_SYSTEM_FIELD_IDS or bool(field.get("is_custom"))
        ]
        normalized_task_fields_by_id = {
            str(field.get("id") or "").strip(): field
            for field in normalized_task_fields
            if str(field.get("id") or "").strip()
        }

        task_userfields_result = None
        try:
            task_userfields_result = unwrap_bitrix_result(
                BitrixAPIRequest(
                    bitrix_token=account,
                    api_method="task.item.userfield.getlist",
                    params={"ORDER": {"SORT": "ASC"}},
                )
            )
        except Exception:
            task_userfields_result = None

        for task_userfield_item in extract_task_userfield_items(task_userfields_result):
            field_id = str(task_userfield_item.get("FIELD_NAME") or "").strip()
            if not field_id:
                continue

            task_userfield_meta = task_userfield_item
            existing_field = normalized_task_fields_by_id.get(field_id)
            user_type_id = str(task_userfield_item.get("USER_TYPE_ID") or "").strip().lower()
            needs_detail_lookup = (
                existing_field is None
                or str(existing_field.get("title") or "").strip().upper() == field_id.upper()
                or (user_type_id == "enumeration" and not isinstance(existing_field.get("items"), list))
                or (user_type_id == "enumeration" and not existing_field.get("items"))
            )
            if needs_detail_lookup:
                raw_task_userfield_id = task_userfield_item.get("ID")
                task_userfield_id = int(raw_task_userfield_id) if str(raw_task_userfield_id or "").strip().isdigit() else raw_task_userfield_id
                if task_userfield_id not in (None, ""):
                    try:
                        task_userfield_meta = unwrap_bitrix_result(
                            BitrixAPIRequest(
                                bitrix_token=account,
                                api_method="task.item.userfield.get",
                                params={"ID": task_userfield_id},
                            )
                        )
                    except Exception:
                        task_userfield_meta = task_userfield_item

            normalized_task_userfield = normalize_task_userfield_result(task_userfield_meta)
            if normalized_task_userfield is None:
                continue

            if existing_field is None:
                normalized_task_fields_by_id[field_id] = normalized_task_userfield
                continue

            existing_title = str(existing_field.get("title") or "").strip()
            if not existing_title or existing_title.upper() == field_id.upper():
                existing_field = {**existing_field, "title": normalized_task_userfield["title"]}

            if not existing_field.get("items") and normalized_task_userfield.get("items"):
                existing_field = {**existing_field, "items": normalized_task_userfield["items"]}

            existing_type = str(existing_field.get("type") or "").strip().lower()
            normalized_type = str(normalized_task_userfield.get("type") or "").strip().lower()
            if existing_type in {"", "string"} and normalized_type not in {"", "string"}:
                existing_field = {**existing_field, "type": normalized_task_userfield["type"]}

            if not existing_field.get("multiple") and normalized_task_userfield.get("multiple"):
                existing_field = {**existing_field, "multiple": normalized_task_userfield["multiple"]}

            if not existing_field.get("required") and normalized_task_userfield.get("required"):
                existing_field = {**existing_field, "required": normalized_task_userfield["required"]}

            normalized_task_fields_by_id[field_id] = {**existing_field, "is_custom": True}

        for static_field in TASK_FIELDS:
            normalized_task_fields_by_id.setdefault(str(static_field["id"]), dict(static_field))

        return sorted(
            normalized_task_fields_by_id.values(),
            key=lambda item: (item["is_custom"], item["title"], item["id"]),
        )

    static_catalog = STATIC_FIELD_CATALOGS.get(entity_type)
    if static_catalog is not None:
        return [dict(field) for field in static_catalog]

    entity_fields_loaders = {
        "lead": lambda client: client.crm.lead.fields().result,
        "contact": lambda client: client.crm.contact.fields().result,
        "company": lambda client: client.crm.company.fields().result,
        "deal": lambda client: client.crm.deal.fields().result,
    }

    linked_import_schema = get_linked_import_schema(entity_type)
    if linked_import_schema is not None:
        source_fields_results = {}
        for linked_entity in linked_import_schema["entities"]:
            source_entity_type = linked_entity["source_entity_type"]
            loader = entity_fields_loaders.get(source_entity_type)
            if loader is None:
                raise ValueError(f"Unsupported linked source entity type: {source_entity_type}")

            source_fields_result = loader(account.client)
            if not isinstance(source_fields_result, dict):
                raise ValueError("Unable to load entity fields")
            source_fields_results[source_entity_type] = source_fields_result

        linked_fields = []
        linked_entity_sort_order = {
            linked_entity["id"]: index
            for index, linked_entity in enumerate(linked_import_schema["entities"])
        }
        for linked_entity in linked_import_schema["entities"]:
            source_entity_type = linked_entity["source_entity_type"]
            source_fields_result = source_fields_results[source_entity_type]
            source_fields = normalize_fields_result(source_fields_result, entity_type=source_entity_type)
            prefix = linked_entity["prefix"]
            entity_label = linked_entity["label"]
            excluded_source_ids = set(linked_entity["excluded_source_ids"])
            for source_field in source_fields:
                source_field_id = str(source_field.get("id") or "")
                if not source_field_id or source_field_id in excluded_source_ids:
                    continue

                linked_fields.append(
                    {
                        **source_field,
                        "id": f"{prefix}{source_field_id}",
                        "title": f"{entity_label} / {source_field['title']}",
                        "linked_entity": linked_entity["id"],
                        "linked_source_id": source_field_id,
                    }
                )

        virtual_fields = [
            {
                "id": "COMPANY__EXTERNAL_KEY",
                "title": "Компания / Внешний ключ (XML_ID)",
                "type": "string",
                "required": False,
                "multiple": False,
                "is_custom": False,
                "linked_entity": "company",
                "linked_source_id": "EXTERNAL_KEY",
            }
        ]
        return virtual_fields + sorted(
            linked_fields,
            key=lambda item: (
                linked_entity_sort_order.get(str(item.get("linked_entity") or "").strip().lower(), len(linked_entity_sort_order)),
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
        smart_status_entity_ids = extract_smart_process_status_entity_ids(fields_result)
        return enrich_smart_process_fields(
            account,
            smart_process_config["entityTypeId"],
            normalized_fields,
            status_entity_ids_by_field=smart_status_entity_ids,
        )

    loader = entity_fields_loaders.get(entity_type)
    if loader is None:
        raise ValueError("Unsupported entity type")

    fields_result = loader(account.client)
    if not isinstance(fields_result, dict):
        raise ValueError("Unable to load entity fields")

    normalized_fields = normalize_fields_result(fields_result, entity_type=entity_type)
    return enrich_standard_crm_status_fields(account, entity_type, normalized_fields)
