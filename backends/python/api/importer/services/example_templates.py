from io import BytesIO
import re
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


EXAMPLE_TEMPLATE_DEFINITIONS = {
    "lead": {
        "sheet_name": "Лиды",
        "filename": "lead-import-example.xlsx",
        "rows": [
            ["Заголовок", "Имя", "Фамилия", "Телефон", "Email"],
            ["Запрос с сайта", "Алиса", "Иванова", "+79990001122", "alice@example.ru"],
            ["Звонок по рекламе", "Иван", "Петров", "+79990003344", "ivan@example.ru"],
        ],
    },
    "contact": {
        "sheet_name": "Контакты",
        "filename": "contact-import-example.xlsx",
        "rows": [
            ["Имя", "Фамилия", "Телефон", "Email"],
            ["Анна", "Смирнова", "+79991112233", "anna@example.ru"],
            ["Дмитрий", "Кузнецов", "+79994445566", "dmitry@example.ru"],
        ],
    },
    "company": {
        "sheet_name": "Компании",
        "filename": "company-import-example.xlsx",
        "rows": [
            ["Название компании", "Телефон", "Email", "Сайт"],
            ["ООО Альфа", "+78005550101", "hello@alpha.ru", "https://alpha.example.ru"],
            ["ООО Вектор", "+78005550102", "info@vector.ru", "https://vector.example.ru"],
        ],
    },
    "deal": {
        "sheet_name": "Сделки",
        "filename": "deal-import-example.xlsx",
        "rows": [
            ["Название сделки", "Сумма", "Валюта", "Стадия"],
            ["Редизайн сайта", "150000", "RUB", "Новая"],
            ["Подключение телефонии", "85000", "RUB", "В работе"],
        ],
    },
    "linked_company_contact": {
        "sheet_name": "Компания и контакт",
        "filename": "linked_company_contact-import-example.xlsx",
        "rows": [
            [
                "Внешний ключ компании",
                "Название компании",
                "Телефон компании",
                "Email компании",
                "Имя контакта",
                "Фамилия контакта",
                "Телефон контакта",
                "Email контакта",
            ],
            [
                "comp_001",
                "ООО Альфа",
                "+78005550101",
                "hello@alpha.ru",
                "Алиса",
                "Иванова",
                "+79990001122",
                "alice@alpha.ru",
            ],
            [
                "comp_001",
                "ООО Альфа",
                "+78005550101",
                "hello@alpha.ru",
                "Борис",
                "Петров",
                "+79990002233",
                "boris@alpha.ru",
            ],
            [
                "comp_002",
                "ООО Вектор",
                "+78005550102",
                "sales@vector.ru",
                "Виктор",
                "Сидоров",
                "+79990003344",
                "victor@vector.ru",
            ],
            [
                "comp_002",
                "ООО Вектор",
                "+78005550102",
                "sales@vector.ru",
                "Дмитрий",
                "Козлов",
                "+79990004455",
                "dmitry@vector.ru",
            ],
        ],
    },
    "linked_company_deal": {
        "sheet_name": "Компания и сделка",
        "filename": "linked_company_deal-import-example.xlsx",
        "rows": [
            [
                "Внешний ключ компании",
                "Название компании",
                "Телефон компании",
                "Название сделки",
                "Сумма",
                "Валюта",
                "Стадия",
            ],
            [
                "comp_001",
                "ООО Альфа",
                "+78005550101",
                "Редизайн сайта",
                "150000",
                "RUB",
                "Новая",
            ],
            [
                "comp_001",
                "ООО Альфа",
                "+78005550101",
                "Подключение телефонии",
                "85000",
                "RUB",
                "В работе",
            ],
            [
                "comp_002",
                "ООО Вектор",
                "+78005550102",
                "Разработка приложения",
                "320000",
                "RUB",
                "Новая",
            ],
            [
                "comp_002",
                "ООО Вектор",
                "+78005550102",
                "Техподдержка",
                "45000",
                "RUB",
                "В работе",
            ],
        ],
    },
    "linked_contact_company": {
        "sheet_name": "Контакт и компания",
        "filename": "linked_contact_company-import-example.xlsx",
        "rows": [
            [
                "Имя контакта",
                "Фамилия контакта",
                "Телефон контакта",
                "Email контакта",
                "Название компании",
                "Телефон компании",
                "Email компании",
            ],
            [
                "Алиса",
                "Иванова",
                "+79990001122",
                "alice@example.ru",
                "ООО Альфа",
                "+78005550101",
                "hello@alpha.ru",
            ],
            [
                "Борис",
                "Петров",
                "+79990002233",
                "boris@example.ru",
                "ООО Альфа",
                "+78005550101",
                "hello@alpha.ru",
            ],
            [
                "Виктор",
                "Сидоров",
                "+79990003344",
                "victor@example.ru",
                "ООО Вектор",
                "+78005550102",
                "info@vector.ru",
            ],
        ],
    },
    "linked_contact_deal": {
        "sheet_name": "Контакт и сделка",
        "filename": "linked_contact_deal-import-example.xlsx",
        "rows": [
            [
                "Внешний ключ контакта",
                "Имя контакта",
                "Фамилия контакта",
                "Телефон контакта",
                "Email контакта",
                "Название сделки",
                "Сумма",
                "Валюта",
                "Стадия",
            ],
            [
                "contact_001",
                "Алиса",
                "Иванова",
                "+79990001122",
                "alice@example.ru",
                "Редизайн сайта",
                "150000",
                "RUB",
                "Новая",
            ],
            [
                "contact_001",
                "Алиса",
                "Иванова",
                "+79990001122",
                "alice@example.ru",
                "Аудит воронки",
                "45000",
                "RUB",
                "В работе",
            ],
            [
                "contact_002",
                "Борис",
                "Петров",
                "+79990002233",
                "boris@example.ru",
                "Подключение телефонии",
                "85000",
                "RUB",
                "Новая",
            ],
        ],
    },
    "linked_deal_company": {
        "sheet_name": "Сделка и компания",
        "filename": "linked_deal_company-import-example.xlsx",
        "rows": [
            [
                "Название сделки",
                "Сумма",
                "Валюта",
                "Стадия",
                "Название компании",
                "Телефон компании",
                "Email компании",
            ],
            [
                "Редизайн сайта",
                "150000",
                "RUB",
                "Новая",
                "ООО Альфа",
                "+78005550101",
                "hello@alpha.ru",
            ],
            [
                "Подключение телефонии",
                "85000",
                "RUB",
                "В работе",
                "ООО Бета",
                "+78005550102",
                "sales@beta.ru",
            ],
            [
                "Аудит воронки",
                "45000",
                "RUB",
                "Новая",
                "ООО Вектор",
                "+78005550103",
                "info@vector.ru",
            ],
        ],
    },
    "linked_deal_contact": {
        "sheet_name": "Сделка и контакты",
        "filename": "linked_deal_contact-import-example.xlsx",
        "rows": [
            [
                "Внешний ключ сделки",
                "Название сделки",
                "Сумма",
                "Валюта",
                "Стадия",
                "Имя контакта",
                "Фамилия контакта",
                "Телефон контакта",
                "Email контакта",
            ],
            [
                "deal_001",
                "Редизайн сайта",
                "150000",
                "RUB",
                "Новая",
                "Алиса",
                "Иванова",
                "+79990001122",
                "alice@example.ru",
            ],
            [
                "deal_001",
                "Редизайн сайта",
                "150000",
                "RUB",
                "Новая",
                "Борис",
                "Петров",
                "+79990002233",
                "boris@example.ru",
            ],
            [
                "deal_002",
                "Аудит воронки",
                "45000",
                "RUB",
                "В работе",
                "Елена",
                "Соколова",
                "+79990003344",
                "elena@example.ru",
            ],
        ],
    },
    "task": {
        "sheet_name": "Задачи",
        "filename": "task-import-example.xlsx",
        "rows": [
            ["Название задачи", "Внешний код", "Родительская задача", "Ответственный", "Крайний срок"],
            ["Подготовить план запуска", "ЗАДАЧА-001", "5001", "59", "20.05.2026 18:00"],
            ["Согласовать смету", "ЗАДАЧА-002", "ЗАДАЧА-001", "73", "22.05.2026 12:00"],
        ],
    },
    "task_comment": {
        "sheet_name": "Комментарии",
        "filename": "task_comment-import-example.xlsx",
        "rows": [
            ["ID задачи", "Пользователь (ID)", "Комментарий"],
            ["ЗАДАЧА-001", "59", "Проверено и согласовано"],
            ["ЗАДАЧА-002", "73", "Нужны правки по срокам"],
        ],
    },
    "task_checklist_item": {
        "sheet_name": "Чек-лист",
        "filename": "task_checklist_item-import-example.xlsx",
        "rows": [
            ["Задача", "Пункт чек-листа", "Выполнено"],
            ["ЗАДАЧА-001", "Согласовать смету", "Нет"],
            ["ЗАДАЧА-001", "Подтвердить запуск", "Да"],
        ],
    },
    "task_attachment": {
        "sheet_name": "Вложения",
        "filename": "task_attachment-import-example.xlsx",
        "rows": [
            ["ID задачи", "Ссылка на файл", "Имя файла"],
            ["ЗАДАЧА-001", "https://files.example.com/brif.pdf", "бриф.pdf"],
            ["ЗАДАЧА-002", "https://files.example.com/smeta.xlsx", "смета.xlsx"],
        ],
    },
    "crm_files_lead": {
        "sheet_name": "Файлы лидов",
        "filename": "crm_files_lead-import-example.xlsx",
        "rows": [
            ["ID лида", "Ссылка на файл", "Имя файла", "ID поля"],
            ["101", "https://files.example.com/brif.pdf", "бриф.pdf", "UF_CRM_1_XXXXXXXX"],
            ["102", "https://files.example.com/contract.pdf", "договор.pdf", "UF_CRM_1_XXXXXXXX"],
        ],
    },
    "crm_files_contact": {
        "sheet_name": "Файлы контактов",
        "filename": "crm_files_contact-import-example.xlsx",
        "rows": [
            ["ID контакта", "Ссылка на файл", "Имя файла", "ID поля"],
            ["201", "https://files.example.com/photo.jpg", "фото.jpg", "UF_CRM_3_XXXXXXXX"],
            ["202", "https://files.example.com/passport.pdf", "паспорт.pdf", "UF_CRM_3_XXXXXXXX"],
        ],
    },
    "crm_files_company": {
        "sheet_name": "Файлы компаний",
        "filename": "crm_files_company-import-example.xlsx",
        "rows": [
            ["ID компании", "Ссылка на файл", "Имя файла", "ID поля"],
            ["301", "https://files.example.com/logo.png", "логотип.png", "UF_CRM_5_XXXXXXXX"],
            ["302", "https://files.example.com/charter.pdf", "устав.pdf", "UF_CRM_5_XXXXXXXX"],
        ],
    },
    "crm_files_deal": {
        "sheet_name": "Файлы сделок",
        "filename": "crm_files_deal-import-example.xlsx",
        "rows": [
            ["ID сделки", "Ссылка на файл", "Имя файла", "ID поля"],
            ["401", "https://files.example.com/smeta.xlsx", "смета.xlsx", "UF_CRM_XXXXXXXX"],
            ["402", "https://files.example.com/act.pdf", "акт.pdf", "UF_CRM_XXXXXXXX"],
        ],
    },
    "user": {
        "sheet_name": "Пользователи",
        "filename": "user-import-example.xlsx",
        "rows": [
            ["Имя", "Фамилия", "Отчество", "Email", "Должность", "Мобильный телефон", "Отдел (ID)", "Активен"],
            ["Алексей", "Иванов", "Николаевич", "a.ivanov@example.ru", "Менеджер по продажам", "+79991234567", "5", "Да"],
            ["Мария", "Петрова", "", "m.petrova@example.ru", "Аналитик", "+79997654321", "7", "Да"],
        ],
    },
    "department": {
        "sheet_name": "Отделы",
        "filename": "department-import-example.xlsx",
        "rows": [
            ["Название отдела", "ID родительского отдела", "Руководитель (ID)", "Сортировка", "Внешний ID"],
            ["Отдел продаж", "", "42", "100", "DEPT-001"],
            ["Розничные продажи", "5", "59", "110", "DEPT-002"],
        ],
    },
    "crm_activity": {
        "sheet_name": "Активности",
        "filename": "crm_activity-import-example.xlsx",
        "rows": [
            ["Тип сущности CRM", "ID записи CRM", "Тип активности", "Тема / заголовок", "Описание", "Дата начала", "Дата окончания", "Телефон / Email (для звонков и писем)"],
            ["Сделка", "55", "Звонок", "Звонок по презентации", "Обсудили условия сотрудничества", "15.05.2026 10:00", "15.05.2026 10:30", "+79991234567"],
            ["Сделка", "55", "Встреча", "Встреча по договору", "Подписание финального варианта", "16.05.2026 14:00", "16.05.2026 15:00", ""],
        ],
    },
    "crm_note": {
        "sheet_name": "Заметки",
        "filename": "crm_note-import-example.xlsx",
        "rows": [
            ["Тип сущности CRM", "ID записи CRM", "Текст заметки", "Дата создания"],
            ["Контакт", "101", "Клиент заинтересован, ждёт коммерческое предложение", "17.05.2026 11:30"],
            ["Сделка", "55", "Договор согласован, ожидаем подписания со стороны клиента", "18.05.2026 15:45"],
        ],
    },
}


def get_example_template_definition(entity_type: str) -> dict:
    normalized_entity_type = str(entity_type or "").strip()
    template_definition = EXAMPLE_TEMPLATE_DEFINITIONS.get(normalized_entity_type)
    if template_definition is None:
        raise ValueError("Unsupported entity type")
    return template_definition


def build_example_template_filename(entity_type: str) -> str:
    return str(get_example_template_definition(entity_type)["filename"])


def build_example_template_xlsx(entity_type: str) -> bytes:
    template_definition = get_example_template_definition(entity_type)
    return build_xlsx_from_definition(template_definition)


def build_smart_process_example_template_filename(entity_config: dict | None = None) -> str:
    normalized_config = entity_config if isinstance(entity_config, dict) else {}
    entity_type_id = int(normalized_config.get("entityTypeId") or 0)
    if entity_type_id <= 0:
        raise ValueError("entity_type_id is required for smart_process")
    return f"smart-process-{entity_type_id}-import-example.xlsx"


def build_smart_process_example_template_xlsx(entity_config: dict | None, fields: list[dict]) -> bytes:
    normalized_config = entity_config if isinstance(entity_config, dict) else {}
    entity_type_id = int(normalized_config.get("entityTypeId") or 0)
    if entity_type_id <= 0:
        raise ValueError("entity_type_id is required for smart_process")

    process_title = str(normalized_config.get("title") or "").strip() or f"Smart Process {entity_type_id}"
    selected_fields = select_smart_process_template_fields(fields)
    rows = [
        [str(field.get("title") or field.get("id") or "") for field in selected_fields],
        [build_smart_process_example_value(field, process_title) for field in selected_fields],
    ]
    template_definition = {
        "sheet_name": build_smart_process_sheet_name(process_title),
        "filename": build_smart_process_example_template_filename(normalized_config),
        "rows": rows,
    }
    return build_xlsx_from_definition(template_definition)


def build_smart_process_sheet_name(process_title: str) -> str:
    normalized_title = re.sub(r"[\\/*?:\\[\\]]+", " ", str(process_title or "")).strip()
    return (normalized_title or "Смарт-процесс")[:31]


def select_smart_process_template_fields(fields: list[dict]) -> list[dict]:
    safe_fields = [field for field in (fields or []) if isinstance(field, dict)]
    prioritized_ids = {"title", "categoryid", "stageid"}
    selected_fields = []
    selected_ids = set()

    for field in safe_fields:
        field_id = str(field.get("id") or "").strip().lower()
        if field_id in prioritized_ids and field_id not in selected_ids:
            selected_fields.append(field)
            selected_ids.add(field_id)

    for field in safe_fields:
        field_id = str(field.get("id") or "").strip().lower()
        if field.get("required") and field_id not in selected_ids:
            selected_fields.append(field)
            selected_ids.add(field_id)

    if selected_fields:
        return selected_fields

    return safe_fields[:3]


def build_smart_process_example_value(field: dict, process_title: str) -> str:
    field_id = str(field.get("id") or "").strip().lower()
    field_type = str(field.get("type") or "string").strip().lower()
    field_items = field.get("items") if isinstance(field.get("items"), list) else []

    if field_items:
        first_item = field_items[0] if isinstance(field_items[0], dict) else {}
        return str(first_item.get("title") or first_item.get("id") or "Значение")

    if field_id == "title":
        return process_title

    if field_type in {"boolean", "bool"}:
        return "Да"
    if field_type in {"integer", "int"}:
        return "1"
    if field_type in {"double", "float", "money", "number"}:
        return "1000"
    if field_type == "date":
        return "20.05.2026"
    if field_type == "datetime":
        return "20.05.2026 10:00"
    if field_type in {"crm_status", "crm_category", "enumeration", "list"}:
        return ""

    return "Пример"


def build_xlsx_from_definition(template_definition: dict) -> bytes:
    sheet_name = str(template_definition["sheet_name"])
    rows = template_definition["rows"]

    workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="{sheet_name}" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
""".format(sheet_name=escape(sheet_name))

    workbook_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>
"""

    root_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""

    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>
"""

    sheet_xml = build_sheet_xml(rows)

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", root_rels_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    return buffer.getvalue()


def build_sheet_xml(rows: list[list]) -> str:
    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells_xml = []
        for column_index, value in enumerate(row, start=1):
            column_letter = build_column_letter(column_index)
            cell_ref = f"{column_letter}{row_index}"
            cells_xml.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
            )
        row_xml.append(f'<row r="{row_index}">{"".join(cells_xml)}</row>')

    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    {rows}
  </sheetData>
</worksheet>
""".format(rows="".join(row_xml))


def build_column_letter(column_index: int) -> str:
    letters = []
    current = int(column_index)
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters))
