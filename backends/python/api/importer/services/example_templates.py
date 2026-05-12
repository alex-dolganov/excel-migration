from io import BytesIO
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
            ["Имя", "Фамилия", "Телефон", "Email", "Компания"],
            ["Анна", "Смирнова", "+79991112233", "anna@example.ru", "ООО Альфа"],
            ["Дмитрий", "Кузнецов", "+79994445566", "dmitry@example.ru", "ООО Вектор"],
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
                "Название компании",
                "Телефон компании",
                "Email компании",
                "Имя контакта",
                "Фамилия контакта",
                "Телефон контакта",
                "Email контакта",
            ],
            [
                "ООО Альфа",
                "+78005550101",
                "hello@alpha.ru",
                "Алиса",
                "Иванова",
                "+79990001122",
                "alice@alpha.ru",
            ],
            [
                "ООО Вектор",
                "+78005550102",
                "sales@vector.ru",
                "Иван",
                "Петров",
                "+79990002233",
                "ivan@vector.ru",
            ],
        ],
    },
    "task": {
        "sheet_name": "Задачи",
        "filename": "task-import-example.xlsx",
        "rows": [
            ["Название задачи", "Внешний ID", "ID родительской задачи", "Ответственный (ID)", "Крайний срок"],
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
            ["ID задачи", "Пункт чек-листа", "Выполнено"],
            ["12345", "Согласовать смету", "Нет"],
            ["12345", "Подтвердить запуск", "Нет"],
            ["12345", "Отправить клиенту", "Да"],
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
            ["Имя", "Фамилия", "Отчество", "Email", "Должность", "Мобильный телефон", "Отдел (ID)", "Активен", "Внешний ID"],
            ["Алексей", "Иванов", "Николаевич", "a.ivanov@example.ru", "Менеджер по продажам", "+79991234567", "5", "Да", "USER-001"],
            ["Мария", "Петрова", "", "m.petrova@example.ru", "Аналитик", "+79997654321", "7", "Да", "USER-002"],
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
