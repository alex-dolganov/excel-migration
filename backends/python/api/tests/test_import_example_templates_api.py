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
                    ["Редизайн сайта", "150000", "Рубли", "Новая"],
                    ["Подключение телефонии", "85000", "Рубли", "В работе"],
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
    def test_viewer_cannot_download_example_template(self, get_from_jwt_token):
        self.create_role(user_id=7, role=ROLE_VIEWER)
        get_from_jwt_token.return_value = self.create_account(is_admin=False)

        response = self.client.get(
            f"{reverse('importer:example-template-xlsx')}?entity_type=deal",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 403)

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
