from io import BytesIO
import re
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from .error_messages import normalize_import_language


# Перевод всех строк русских определений шаблонов (en / br).
# Значения без перевода (телефоны, ID, даты, URL, email) проходят как есть.
TEMPLATE_VALUE_TRANSLATIONS = {
    # Имена листов
    "Лиды": {"en": "Leads", "br": "Leads"},
    "Контакты": {"en": "Contacts", "br": "Contatos"},
    "Компании": {"en": "Companies", "br": "Empresas"},
    "Сделки": {"en": "Deals", "br": "Negócios"},
    "Компания и контакт": {"en": "Company and contact", "br": "Empresa e contato"},
    "Компания и сделка": {"en": "Company and deal", "br": "Empresa e negócio"},
    "Контакт и компания": {"en": "Contact and company", "br": "Contato e empresa"},
    "Контакт и сделка": {"en": "Contact and deal", "br": "Contato e negócio"},
    "Сделка и компания": {"en": "Deal and company", "br": "Negócio e empresa"},
    "Сделка и контакты": {"en": "Deal and contacts", "br": "Negócio e contatos"},
    "Задачи": {"en": "Tasks", "br": "Tarefas"},
    "Комментарии": {"en": "Comments", "br": "Comentários"},
    "Чек-лист": {"en": "Checklist", "br": "Checklist"},
    "Вложения": {"en": "Attachments", "br": "Anexos"},
    "Файлы лидов": {"en": "Lead files", "br": "Arquivos de leads"},
    "Файлы контактов": {"en": "Contact files", "br": "Arquivos de contatos"},
    "Файлы компаний": {"en": "Company files", "br": "Arquivos de empresas"},
    "Файлы сделок": {"en": "Deal files", "br": "Arquivos de negócios"},
    "Пользователи": {"en": "Users", "br": "Usuários"},
    "Отделы": {"en": "Departments", "br": "Departamentos"},
    "Активности": {"en": "Activities", "br": "Atividades"},
    "Заметки": {"en": "Notes", "br": "Notas"},
    "Смарт-процесс": {"en": "Smart Process", "br": "Processo inteligente"},
    # Заголовки колонок
    "Заголовок": {"en": "Title", "br": "Título"},
    "Имя": {"en": "First name", "br": "Nome"},
    "Фамилия": {"en": "Last name", "br": "Sobrenome"},
    "Телефон": {"en": "Phone", "br": "Telefone"},
    "Название компании": {"en": "Company name", "br": "Nome da empresa"},
    "Сайт": {"en": "Website", "br": "Site"},
    "Название сделки": {"en": "Deal name", "br": "Nome do negócio"},
    "Сумма": {"en": "Amount", "br": "Valor"},
    "Валюта": {"en": "Currency", "br": "Moeda"},
    "Стадия": {"en": "Stage", "br": "Etapa"},
    "Внешний ключ компании": {"en": "Company external key", "br": "Chave externa da empresa"},
    "Телефон компании": {"en": "Company phone", "br": "Telefone da empresa"},
    "Email компании": {"en": "Company email", "br": "Email da empresa"},
    "Имя контакта": {"en": "Contact first name", "br": "Nome do contato"},
    "Фамилия контакта": {"en": "Contact last name", "br": "Sobrenome do contato"},
    "Телефон контакта": {"en": "Contact phone", "br": "Telefone do contato"},
    "Email контакта": {"en": "Contact email", "br": "Email do contato"},
    "Внешний ключ контакта": {"en": "Contact external key", "br": "Chave externa do contato"},
    "Внешний ключ сделки": {"en": "Deal external key", "br": "Chave externa do negócio"},
    "Название задачи": {"en": "Task name", "br": "Nome da tarefa"},
    "Ответственный": {"en": "Assignee", "br": "Responsável"},
    "Крайний срок": {"en": "Deadline", "br": "Prazo"},
    "ID задачи": {"en": "Task ID", "br": "ID da tarefa"},
    "Пользователь (ID)": {"en": "User (ID)", "br": "Usuário (ID)"},
    "Комментарий": {"en": "Comment", "br": "Comentário"},
    "Пункт чек-листа": {"en": "Checklist item", "br": "Item do checklist"},
    "Выполнено": {"en": "Completed", "br": "Concluído"},
    "Ссылка на файл": {"en": "File URL", "br": "Link do arquivo"},
    "Имя файла": {"en": "File name", "br": "Nome do arquivo"},
    "ID лида": {"en": "Lead ID", "br": "ID do lead"},
    "ID поля": {"en": "Field ID", "br": "ID do campo"},
    "ID контакта": {"en": "Contact ID", "br": "ID do contato"},
    "ID компании": {"en": "Company ID", "br": "ID da empresa"},
    "ID сделки": {"en": "Deal ID", "br": "ID do negócio"},
    "Отчество": {"en": "Middle name", "br": "Nome do meio"},
    "Должность": {"en": "Position", "br": "Cargo"},
    "Мобильный телефон": {"en": "Mobile phone", "br": "Telefone celular"},
    "Отдел (ID)": {"en": "Department (ID)", "br": "Departamento (ID)"},
    "Активен": {"en": "Active", "br": "Ativo"},
    "Название отдела": {"en": "Department name", "br": "Nome do departamento"},
    "ID родительского отдела": {"en": "Parent department ID", "br": "ID do departamento superior"},
    "Руководитель (ID)": {"en": "Manager (ID)", "br": "Gerente (ID)"},
    "Сортировка": {"en": "Sort order", "br": "Ordenação"},
    "Внешний ID": {"en": "External ID", "br": "ID externo"},
    "Тип сущности CRM": {"en": "CRM entity type", "br": "Tipo de entidade CRM"},
    "ID записи CRM": {"en": "CRM record ID", "br": "ID do registro CRM"},
    "Тип активности": {"en": "Activity type", "br": "Tipo de atividade"},
    "Тема / заголовок": {"en": "Subject / title", "br": "Assunto / título"},
    "Описание": {"en": "Description", "br": "Descrição"},
    "Дата начала": {"en": "Start date", "br": "Data de início"},
    "Дата окончания": {"en": "End date", "br": "Data de término"},
    "Телефон / Email (для звонков и писем)": {
        "en": "Phone / Email (for calls and emails)",
        "br": "Telefone / Email (para ligações e emails)",
    },
    "Текст заметки": {"en": "Note text", "br": "Texto da nota"},
    "Дата создания": {"en": "Created on", "br": "Data de criação"},
    # Значения-примеры
    "Запрос с сайта": {"en": "Website inquiry", "br": "Solicitação do site"},
    "Звонок по рекламе": {"en": "Ad campaign call", "br": "Ligação de anúncio"},
    "Алиса": {"en": "Alice", "br": "Alice"},
    "Иванова": {"en": "Johnson", "br": "Silva"},
    "Иван": {"en": "John", "br": "João"},
    "Петров": {"en": "Peters", "br": "Santos"},
    "Петрова": {"en": "Peters", "br": "Santos"},
    "Анна": {"en": "Anna", "br": "Ana"},
    "Смирнова": {"en": "Smith", "br": "Souza"},
    "Дмитрий": {"en": "Daniel", "br": "Daniel"},
    "Кузнецов": {"en": "Cooper", "br": "Oliveira"},
    "Борис": {"en": "Brian", "br": "Bruno"},
    "Виктор": {"en": "Victor", "br": "Vitor"},
    "Сидоров": {"en": "Simmons", "br": "Pereira"},
    "Козлов": {"en": "Collins", "br": "Costa"},
    "Елена": {"en": "Helen", "br": "Helena"},
    "Соколова": {"en": "Foster", "br": "Ferreira"},
    "Алексей": {"en": "Alex", "br": "Alex"},
    "Иванов": {"en": "Johnson", "br": "Silva"},
    "Николаевич": {"en": "Nicholas", "br": "Nicolau"},
    "Мария": {"en": "Mary", "br": "Maria"},
    "ООО Альфа": {"en": "Alpha LLC", "br": "Alpha Ltda"},
    "ООО Вектор": {"en": "Vector LLC", "br": "Vector Ltda"},
    "ООО Бета": {"en": "Beta LLC", "br": "Beta Ltda"},
    "Редизайн сайта": {"en": "Website redesign", "br": "Redesign do site"},
    "Подключение телефонии": {"en": "Telephony setup", "br": "Implantação de telefonia"},
    "Разработка приложения": {"en": "App development", "br": "Desenvolvimento de aplicativo"},
    "Техподдержка": {"en": "Tech support", "br": "Suporte técnico"},
    "Аудит воронки": {"en": "Funnel audit", "br": "Auditoria do funil"},
    "Новая": {"en": "New", "br": "Novo"},
    "В работе": {"en": "In progress", "br": "Em andamento"},
    "RUB": {"en": "USD", "br": "BRL"},
    "Подготовить план запуска": {"en": "Prepare launch plan", "br": "Preparar plano de lançamento"},
    "Согласовать смету": {"en": "Approve the estimate", "br": "Aprovar o orçamento"},
    "Проверено и согласовано": {"en": "Reviewed and approved", "br": "Revisado e aprovado"},
    "Нужны правки по срокам": {"en": "Timeline needs changes", "br": "Prazos precisam de ajustes"},
    "Подтвердить запуск": {"en": "Confirm launch", "br": "Confirmar lançamento"},
    "Да": {"en": "Yes", "br": "Sim"},
    "Нет": {"en": "No", "br": "Não"},
    "ЗАДАЧА-001": {"en": "TASK-001", "br": "TAREFA-001"},
    "ЗАДАЧА-002": {"en": "TASK-002", "br": "TAREFA-002"},
    "бриф.pdf": {"en": "brief.pdf", "br": "briefing.pdf"},
    "смета.xlsx": {"en": "estimate.xlsx", "br": "orcamento.xlsx"},
    "договор.pdf": {"en": "contract.pdf", "br": "contrato.pdf"},
    "фото.jpg": {"en": "photo.jpg", "br": "foto.jpg"},
    "паспорт.pdf": {"en": "passport.pdf", "br": "documento.pdf"},
    "логотип.png": {"en": "logo.png", "br": "logotipo.png"},
    "устав.pdf": {"en": "charter.pdf", "br": "estatuto.pdf"},
    "акт.pdf": {"en": "act.pdf", "br": "termo.pdf"},
    "Менеджер по продажам": {"en": "Sales manager", "br": "Gerente de vendas"},
    "Аналитик": {"en": "Analyst", "br": "Analista"},
    "Отдел продаж": {"en": "Sales department", "br": "Departamento de vendas"},
    "Розничные продажи": {"en": "Retail sales", "br": "Vendas no varejo"},
    "Сделка": {"en": "Deal", "br": "Negócio"},
    "Контакт": {"en": "Contact", "br": "Contato"},
    "Звонок": {"en": "Call", "br": "Ligação"},
    "Встреча": {"en": "Meeting", "br": "Reunião"},
    "Звонок по презентации": {"en": "Call about the presentation", "br": "Ligação sobre a apresentação"},
    "Обсудили условия сотрудничества": {"en": "Discussed cooperation terms", "br": "Discutimos as condições de parceria"},
    "Встреча по договору": {"en": "Contract meeting", "br": "Reunião sobre o contrato"},
    "Подписание финального варианта": {"en": "Signing the final version", "br": "Assinatura da versão final"},
    "Клиент заинтересован, ждёт коммерческое предложение": {
        "en": "Client is interested, waiting for a quote",
        "br": "Cliente interessado, aguardando proposta comercial",
    },
    "Договор согласован, ожидаем подписания со стороны клиента": {
        "en": "Contract approved, waiting for the client to sign",
        "br": "Contrato aprovado, aguardando assinatura do cliente",
    },
    "Значение": {"en": "Value", "br": "Valor"},
    "Пример": {"en": "Example", "br": "Exemplo"},
}


def translate_template_value(value, language: str):
    if language == "ru":
        return value
    translations = TEMPLATE_VALUE_TRANSLATIONS.get(str(value))
    if not translations:
        return value
    return translations.get(language, value)


def localize_template_definition(template_definition: dict, language: str) -> dict:
    normalized_language = normalize_import_language(language)
    if normalized_language == "ru":
        return template_definition
    return {
        **template_definition,
        "sheet_name": translate_template_value(template_definition["sheet_name"], normalized_language),
        "rows": [
            [translate_template_value(value, normalized_language) for value in row]
            for row in template_definition["rows"]
        ],
    }


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
            ["Название задачи", "Ответственный", "Крайний срок"],
            ["Подготовить план запуска", "59", "20.05.2026 18:00"],
            ["Согласовать смету", "73", "22.05.2026 12:00"],
        ],
    },
    "task_comment": {
        "sheet_name": "Комментарии",
        "filename": "task_comment-import-example.xlsx",
        "rows": [
            ["ID задачи", "Пользователь (ID)", "Комментарий"],
            ["1001", "59", "Проверено и согласовано"],
            ["1002", "73", "Нужны правки по срокам"],
        ],
    },
    "task_checklist_item": {
        "sheet_name": "Чек-лист",
        "filename": "task_checklist_item-import-example.xlsx",
        "rows": [
            ["ID задачи", "Пункт чек-листа", "Выполнено"],
            ["1001", "Согласовать смету", "Нет"],
            ["1001", "Подтвердить запуск", "Да"],
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


def build_example_template_xlsx(entity_type: str, language: str = "ru") -> bytes:
    template_definition = get_example_template_definition(entity_type)
    return build_xlsx_from_definition(localize_template_definition(template_definition, language))


def build_smart_process_example_template_filename(entity_config: dict | None = None) -> str:
    normalized_config = entity_config if isinstance(entity_config, dict) else {}
    entity_type_id = int(normalized_config.get("entityTypeId") or 0)
    if entity_type_id <= 0:
        raise ValueError("entity_type_id is required for smart_process")
    return f"smart-process-{entity_type_id}-import-example.xlsx"


def build_smart_process_example_template_xlsx(entity_config: dict | None, fields: list[dict], language: str = "ru") -> bytes:
    normalized_config = entity_config if isinstance(entity_config, dict) else {}
    entity_type_id = int(normalized_config.get("entityTypeId") or 0)
    if entity_type_id <= 0:
        raise ValueError("entity_type_id is required for smart_process")

    normalized_language = normalize_import_language(language)
    process_title = str(normalized_config.get("title") or "").strip() or f"Smart Process {entity_type_id}"
    selected_fields = select_smart_process_template_fields(fields)
    rows = [
        [str(field.get("title") or field.get("id") or "") for field in selected_fields],
        [
            translate_template_value(build_smart_process_example_value(field, process_title), normalized_language)
            for field in selected_fields
        ],
    ]
    template_definition = {
        "sheet_name": translate_template_value(build_smart_process_sheet_name(process_title), normalized_language),
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
