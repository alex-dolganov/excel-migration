from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

from django.test import TestCase
from django.urls import reverse

from importer.models import ImporterUserRole
from importer.services.permissions import ROLE_OPERATOR, ROLE_VIEWER


def read_sheet_xml_from_xlsx(content: bytes) -> str:
    with ZipFile(BytesIO(content), "r") as archive:
        return archive.read("xl/worksheets/sheet1.xml").decode("utf-8")


class ImportExampleTemplatesApiTest(TestCase):
    def create_account(self, *, user_id=7, is_admin=False, member_id="member-1", domain_url="test.bitrix24.ru"):
        return SimpleNamespace(
            member_id=member_id,
            domain_url=domain_url,
            b24_user_id=user_id,
            is_b24_user_admin=is_admin,
        )

    def create_role(self, *, user_id=7, role=ROLE_VIEWER, granted_by=1, member_id="member-1", domain_url="test.bitrix24.ru"):
        return ImporterUserRole.objects.create(
            portal_member_id=member_id,
            portal_domain=domain_url,
            b24_user_id=user_id,
            role=role,
            granted_by_b24_user_id=granted_by,
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_operator_can_download_example_templates_for_deal_task_and_checklist(self, get_from_jwt_token):
        self.create_role(user_id=7, role=ROLE_OPERATOR)
        get_from_jwt_token.return_value = self.create_account(is_admin=False)

        expected_cases = [
            (
                "deal",
                ["Название сделки", "Сумма", "Валюта", "Стадия"],
                [
                    ["Редизайн сайта", "150000", "RUB", "Новая"],
                    ["Подключение телефонии", "85000", "RUB", "В работе"],
                ],
                ["TITLE", "Website redesign"],
            ),
            (
                "task",
                ["Название задачи", "Внешний код", "Родительская задача", "Ответственный", "Крайний срок"],
                [
                    ["Подготовить план запуска", "ЗАДАЧА-001", "5001", "59", "20.05.2026 18:00"],
                    ["Согласовать смету", "ЗАДАЧА-002", "ЗАДАЧА-001", "73", "22.05.2026 12:00"],
                ],
                ["TITLE", "Prepare launch plan"],
            ),
            (
                "task_checklist_item",
                ["Задача", "Пункт чек-листа", "Выполнено"],
                [
                    ["ЗАДАЧА-001", "Согласовать смету", "Нет"],
                    ["ЗАДАЧА-001", "Подтвердить запуск", "Да"],
                ],
                ["TASK_ID", "Approve estimate"],
            ),
        ]

        for entity_type, expected_headers, expected_rows, unexpected_values in expected_cases:
            response = self.client.get(
                f"{reverse('importer:example-template-xlsx')}?entity_type={entity_type}",
                HTTP_AUTHORIZATION="Bearer test-token",
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response["Content-Type"],
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            self.assertIn("attachment;", response["Content-Disposition"])
            self.assertIn(f"{entity_type}-import-example.xlsx", response["Content-Disposition"])

            sheet_xml = read_sheet_xml_from_xlsx(response.content)
            self.assertEqual(sheet_xml.count("<row r="), 3)
            for value in expected_headers:
                self.assertIn(str(value), sheet_xml)
            for expected_row in expected_rows:
                for value in expected_row:
                    self.assertIn(str(value), sheet_xml)
            for value in unexpected_values:
                self.assertNotIn(str(value), sheet_xml)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_viewer_can_download_example_template_when_import_access_is_open(self, get_from_jwt_token):
        self.create_role(user_id=7, role=ROLE_VIEWER)
        get_from_jwt_token.return_value = self.create_account(is_admin=False)

        response = self.client.get(
            f"{reverse('importer:example-template-xlsx')}?entity_type=deal",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_download_example_template_rejects_unknown_entity_type(self, get_from_jwt_token):
        self.create_role(user_id=7, role=ROLE_OPERATOR)
        get_from_jwt_token.return_value = self.create_account(is_admin=False)

        response = self.client.get(
            f"{reverse('importer:example-template-xlsx')}?entity_type=unknown_entity",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Unsupported entity type")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_operator_can_download_example_template_for_linked_company_contact(self, get_from_jwt_token):
        self.create_role(user_id=7, role=ROLE_OPERATOR)
        get_from_jwt_token.return_value = self.create_account(is_admin=False)

        response = self.client.get(
            f"{reverse('importer:example-template-xlsx')}?entity_type=linked_company_contact",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("linked_company_contact-import-example.xlsx", response["Content-Disposition"])

        sheet_xml = read_sheet_xml_from_xlsx(response.content)
        for value in [
            "Название компании",
            "Телефон компании",
            "Email компании",
            "Имя контакта",
            "Фамилия контакта",
            "Телефон контакта",
            "Email контакта",
        ]:
            self.assertIn(value, sheet_xml)

        for value in [
            "ООО Альфа",
            "+78005550101",
            "alice@alpha.ru",
            "Алиса",
            "Иванова",
            "+79990001122",
        ]:
            self.assertIn(value, sheet_xml)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_operator_can_download_example_template_for_linked_company_deal(self, get_from_jwt_token):
        self.create_role(user_id=7, role=ROLE_OPERATOR)
        get_from_jwt_token.return_value = self.create_account(is_admin=False)

        response = self.client.get(
            f"{reverse('importer:example-template-xlsx')}?entity_type=linked_company_deal",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("linked_company_deal-import-example.xlsx", response["Content-Disposition"])

        sheet_xml = read_sheet_xml_from_xlsx(response.content)
        for value in [
            "Название компании",
            "Телефон компании",
            "Название сделки",
            "Сумма",
            "Валюта",
            "Стадия",
        ]:
            self.assertIn(value, sheet_xml)

        for value in [
            "ООО Альфа",
            "+78005550101",
            "Редизайн сайта",
            "150000",
            "RUB",
        ]:
            self.assertIn(value, sheet_xml)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_operator_can_download_example_template_for_linked_contact_deal(self, get_from_jwt_token):
        self.create_role(user_id=7, role=ROLE_OPERATOR)
        get_from_jwt_token.return_value = self.create_account(is_admin=False)

        response = self.client.get(
            f"{reverse('importer:example-template-xlsx')}?entity_type=linked_contact_deal",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("linked_contact_deal-import-example.xlsx", response["Content-Disposition"])

        sheet_xml = read_sheet_xml_from_xlsx(response.content)
        for value in [
            "Внешний ключ контакта",
            "Имя контакта",
            "Фамилия контакта",
            "Телефон контакта",
            "Название сделки",
            "Сумма",
            "Валюта",
            "Стадия",
        ]:
            self.assertIn(value, sheet_xml)

        for value in [
            "contact_001",
            "Алиса",
            "Иванова",
            "+79990001122",
            "Редизайн сайта",
            "150000",
            "RUB",
        ]:
            self.assertIn(value, sheet_xml)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_operator_can_download_example_template_for_linked_contact_company(self, get_from_jwt_token):
        self.create_role(user_id=7, role=ROLE_OPERATOR)
        get_from_jwt_token.return_value = self.create_account(is_admin=False)

        response = self.client.get(
            f"{reverse('importer:example-template-xlsx')}?entity_type=linked_contact_company",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("linked_contact_company-import-example.xlsx", response["Content-Disposition"])

        sheet_xml = read_sheet_xml_from_xlsx(response.content)
        for value in [
            "Имя контакта",
            "Фамилия контакта",
            "Телефон контакта",
            "Название компании",
            "Телефон компании",
            "Email компании",
        ]:
            self.assertIn(value, sheet_xml)

        self.assertNotIn("Внешний ключ контакта", sheet_xml)

        for value in [
            "Алиса",
            "Иванова",
            "+79990001122",
            "Борис",
            "Петров",
            "ООО Альфа",
            "+78005550101",
        ]:
            self.assertIn(value, sheet_xml)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_operator_can_download_example_template_for_linked_deal_company(self, get_from_jwt_token):
        self.create_role(user_id=7, role=ROLE_OPERATOR)
        get_from_jwt_token.return_value = self.create_account(is_admin=False)

        response = self.client.get(
            f"{reverse('importer:example-template-xlsx')}?entity_type=linked_deal_company",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("linked_deal_company-import-example.xlsx", response["Content-Disposition"])

        sheet_xml = read_sheet_xml_from_xlsx(response.content)
        for value in [
            "Название сделки",
            "Сумма",
            "Валюта",
            "Стадия",
            "Название компании",
            "Телефон компании",
            "Email компании",
        ]:
            self.assertIn(value, sheet_xml)
        self.assertNotIn("Внешний ключ сделки", sheet_xml)

        for value in [
            "Редизайн сайта",
            "150000",
            "RUB",
            "ООО Альфа",
            "+78005550101",
        ]:
            self.assertIn(value, sheet_xml)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_operator_can_download_contact_example_template_without_company_name_column(self, get_from_jwt_token):
        self.create_role(user_id=7, role=ROLE_OPERATOR)
        get_from_jwt_token.return_value = self.create_account(is_admin=False)

        response = self.client.get(
            f"{reverse('importer:example-template-xlsx')}?entity_type=contact",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("contact-import-example.xlsx", response["Content-Disposition"])

        sheet_xml = read_sheet_xml_from_xlsx(response.content)
        for value in [
            "Имя",
            "Фамилия",
            "Телефон",
            "Email",
            "Анна",
            "Смирнова",
            "+79991112233",
            "anna@example.ru",
        ]:
            self.assertIn(value, sheet_xml)

        for value in [
            "Компания",
            "Название компании",
            "ООО Альфа",
            "ООО Вектор",
        ]:
            self.assertNotIn(value, sheet_xml)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_operator_can_download_example_template_for_crm_activity_with_communications_value(self, get_from_jwt_token):
        self.create_role(user_id=7, role=ROLE_OPERATOR)
        get_from_jwt_token.return_value = self.create_account(is_admin=False)

        response = self.client.get(
            f"{reverse('importer:example-template-xlsx')}?entity_type=crm_activity",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("crm_activity-import-example.xlsx", response["Content-Disposition"])

        sheet_xml = read_sheet_xml_from_xlsx(response.content)
        for value in [
            "Тип сущности CRM",
            "Тип активности",
            "Телефон / Email (для звонков и писем)",
            "Звонок по презентации",
            "+79991234567",
        ]:
            self.assertIn(value, sheet_xml)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_operator_can_download_example_template_for_crm_note_with_russian_entity_values(self, get_from_jwt_token):
        self.create_role(user_id=7, role=ROLE_OPERATOR)
        get_from_jwt_token.return_value = self.create_account(is_admin=False)

        response = self.client.get(
            f"{reverse('importer:example-template-xlsx')}?entity_type=crm_note",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("crm_note-import-example.xlsx", response["Content-Disposition"])

        sheet_xml = read_sheet_xml_from_xlsx(response.content)
        for value in [
            "Тип сущности CRM",
            "Текст заметки",
            "Дата создания",
            "Контакт",
            "Сделка",
            "17.05.2026 11:30",
        ]:
            self.assertIn(value, sheet_xml)
        for value in [
            "contact",
            "deal",
        ]:
            self.assertNotIn(value, sheet_xml)

    @patch("importer.views.fetch_entity_fields")
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_operator_can_download_dynamic_example_template_for_smart_process(self, get_from_jwt_token, fetch_entity_fields):
        self.create_role(user_id=7, role=ROLE_OPERATOR)
        account = self.create_account(is_admin=False)
        get_from_jwt_token.return_value = account
        fetch_entity_fields.return_value = [
            {
                "id": "title",
                "title": "Название",
                "type": "string",
                "required": True,
                "multiple": False,
                "is_custom": False,
                "items": [],
            },
            {
                "id": "categoryId",
                "title": "Воронка",
                "type": "crm_category",
                "required": True,
                "multiple": False,
                "is_custom": False,
                "items": [
                    {"id": "0", "title": "Основная"},
                    {"id": "7", "title": "Повторные продажи"},
                ],
            },
            {
                "id": "stageId",
                "title": "Стадия",
                "type": "crm_status",
                "required": True,
                "multiple": False,
                "is_custom": False,
                "items": [
                    {"id": "DT128_0:NEW", "title": "Новая"},
                    {"id": "DT128_7:PREPARE", "title": "Подготовка"},
                ],
            },
            {
                "id": "ufCrmAmount",
                "title": "Сумма",
                "type": "double",
                "required": False,
                "multiple": False,
                "is_custom": True,
                "items": [],
            },
        ]

        response = self.client.get(
            f"{reverse('importer:example-template-xlsx')}?entity_type=smart_process&entity_type_id=128&entity_title=%D0%A1%D0%BE%D0%B3%D0%BB%D0%B0%D1%81%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D1%8F",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("smart-process-128-import-example.xlsx", response["Content-Disposition"])

        sheet_xml = read_sheet_xml_from_xlsx(response.content)
        self.assertEqual(sheet_xml.count("<row r="), 2)
        for value in [
            "Название",
            "Воронка",
            "Стадия",
            "Согласования",
            "Основная",
            "Новая",
        ]:
            self.assertIn(value, sheet_xml)
        self.assertNotIn("Сумма", sheet_xml)

        fetch_entity_fields.assert_called_once_with(
            account,
            "smart_process",
            entity_config={
                "entityTypeId": 128,
                "title": "Согласования",
            },
        )

    @patch("importer.views.fetch_entity_fields")
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_smart_process_template_keeps_title_and_stage_when_only_boolean_is_required(self, get_from_jwt_token, fetch_entity_fields):
        self.create_role(user_id=7, role=ROLE_OPERATOR)
        account = self.create_account(is_admin=False)
        get_from_jwt_token.return_value = account
        fetch_entity_fields.return_value = [
            {
                "id": "title",
                "title": "Название",
                "type": "string",
                "required": False,
                "multiple": False,
                "is_custom": False,
                "items": [],
            },
            {
                "id": "stageId",
                "title": "Стадия",
                "type": "crm_status",
                "required": False,
                "multiple": False,
                "is_custom": False,
                "items": [
                    {"id": "DT128_0:NEW", "title": "Новая"},
                ],
            },
            {
                "id": "availableForAll",
                "title": "Доступно для всех",
                "type": "boolean",
                "required": True,
                "multiple": False,
                "is_custom": False,
                "items": [],
            },
        ]

        response = self.client.get(
            f"{reverse('importer:example-template-xlsx')}?entity_type=smart_process&entity_type_id=128&entity_title=%D0%A1%D0%BE%D0%B3%D0%BB%D0%B0%D1%81%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D1%8F",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        sheet_xml = read_sheet_xml_from_xlsx(response.content)
        for value in [
            "Название",
            "Стадия",
            "Доступно для всех",
            "Согласования",
            "Новая",
            "Да",
        ]:
            self.assertIn(value, sheet_xml)

    @patch("importer.views.fetch_entity_fields")
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_smart_process_template_does_not_use_placeholder_for_stage_without_items(self, get_from_jwt_token, fetch_entity_fields):
        self.create_role(user_id=7, role=ROLE_OPERATOR)
        account = self.create_account(is_admin=False)
        get_from_jwt_token.return_value = account
        fetch_entity_fields.return_value = [
            {
                "id": "title",
                "title": "Название",
                "type": "string",
                "required": True,
                "multiple": False,
                "is_custom": False,
                "items": [],
            },
            {
                "id": "stageId",
                "title": "Стадия",
                "type": "crm_status",
                "required": True,
                "multiple": False,
                "is_custom": False,
                "items": [],
            },
        ]

        response = self.client.get(
            f"{reverse('importer:example-template-xlsx')}?entity_type=smart_process&entity_type_id=128&entity_title=%D0%A1%D0%BE%D0%B3%D0%BB%D0%B0%D1%81%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D1%8F",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        sheet_xml = read_sheet_xml_from_xlsx(response.content)
        self.assertIn("Название", sheet_xml)
        self.assertIn("Стадия", sheet_xml)
        self.assertIn("Согласования", sheet_xml)
        self.assertNotIn("Пример", sheet_xml)
