from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class FakeFieldsRequest:
    def __init__(self, result):
        self.result = result


class ImportFieldCatalogApiTest(TestCase):
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_normalized_lead_fields_catalog(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                crm=SimpleNamespace(
                    lead=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "TITLE": {
                                    "title": "Lead title",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "UF_CRM_CUSTOM_TEXT": {
                                    "title": "Custom text",
                                    "type": "string",
                                    "isRequired": False,
                                    "isMultiple": True,
                                    "items": {
                                        "A": "Alpha",
                                        "B": "Beta",
                                    },
                                },
                            }
                        )
                    )
                )
            ),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "lead"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["entity_type"], "lead")
        self.assertEqual(
            response.json()["items"],
            [
                {
                    "id": "TITLE",
                    "title": "Lead title",
                    "type": "string",
                    "required": True,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "UF_CRM_CUSTOM_TEXT",
                    "title": "Custom text",
                    "type": "string",
                    "required": False,
                    "multiple": True,
                    "is_custom": True,
                    "items": [
                        {"id": "A", "title": "Alpha"},
                        {"id": "B", "title": "Beta"},
                    ],
                },
            ],
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_contact_name_fields_as_non_required_in_normalized_catalog(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                crm=SimpleNamespace(
                    contact=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "NAME": {
                                    "title": "First name",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "LAST_NAME": {
                                    "title": "Last name",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "SECOND_NAME": {
                                    "title": "Middle name",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                            }
                        )
                    )
                )
            ),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "contact"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["items"],
            [
                {
                    "id": "NAME",
                    "title": "First name",
                    "type": "string",
                    "required": False,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "LAST_NAME",
                    "title": "Last name",
                    "type": "string",
                    "required": False,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "SECOND_NAME",
                    "title": "Middle name",
                    "type": "string",
                    "required": False,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
            ],
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_static_task_fields_catalog(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "task"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["entity_type"], "task")
        self.assertEqual(
            response.json()["items"],
            [
                {
                    "id": "TITLE",
                    "title": "Task title",
                    "type": "string",
                    "required": True,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "DESCRIPTION",
                    "title": "Description",
                    "type": "text",
                    "required": False,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "RESPONSIBLE_ID",
                    "title": "Responsible user ID",
                    "type": "integer",
                    "required": False,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "ACCOMPLICES",
                    "title": "Accomplice user IDs",
                    "type": "integer",
                    "required": False,
                    "multiple": True,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "AUDITORS",
                    "title": "Auditor user IDs",
                    "type": "integer",
                    "required": False,
                    "multiple": True,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "CREATED_BY",
                    "title": "Creator user ID",
                    "type": "integer",
                    "required": False,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "GROUP_ID",
                    "title": "Project group ID",
                    "type": "integer",
                    "required": False,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "PRIORITY",
                    "title": "Priority",
                    "type": "integer",
                    "required": False,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "TAGS",
                    "title": "Tags",
                    "type": "string",
                    "required": False,
                    "multiple": True,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "DEADLINE",
                    "title": "Deadline",
                    "type": "datetime",
                    "required": False,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "START_DATE_PLAN",
                    "title": "Planned start date",
                    "type": "datetime",
                    "required": False,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "END_DATE_PLAN",
                    "title": "Planned end date",
                    "type": "datetime",
                    "required": False,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "XML_ID",
                    "title": "External ID",
                    "type": "string",
                    "required": False,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "PARENT_ID",
                    "title": "Parent task ID",
                    "type": "integer",
                    "required": False,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
            ],
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_static_crm_activity_fields_catalog_with_communications_value(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "crm_activity"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["entity_type"], "crm_activity")

        items = response.json()["items"]
        owner_type_field = next(item for item in items if item["id"] == "OWNER_TYPE_ID")
        communications_field = next(item for item in items if item["id"] == "COMMUNICATIONS_VALUE")

        self.assertEqual(
            owner_type_field["items"],
            [
                {"id": "1", "title": "Лид"},
                {"id": "2", "title": "Сделка"},
                {"id": "3", "title": "Контакт"},
                {"id": "4", "title": "Компания"},
            ],
        )
        self.assertEqual(communications_field["title"], "Телефон / Email (для звонков и писем)")
        self.assertFalse(communications_field["required"])

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_static_task_comment_fields_catalog(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "task_comment"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["entity_type"], "task_comment")
        self.assertEqual(
            response.json()["items"],
            [
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
            ],
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_task_fields_catalog_marks_responsible_as_required(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "task"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        responsible_field = next(
            item
            for item in response.json()["items"]
            if item["id"] == "RESPONSIBLE_ID"
        )
        self.assertEqual(responsible_field["required"], True)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_static_task_checklist_item_fields_catalog(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "task_checklist_item"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["entity_type"], "task_checklist_item")
        self.assertEqual(
            response.json()["items"],
            [
                {
                    "id": "TASK_ID",
                    "title": "Task ID",
                    "type": "integer",
                    "required": True,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "TITLE",
                    "title": "Checklist item title",
                    "type": "string",
                    "required": True,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "IS_COMPLETE",
                    "title": "Is complete",
                    "type": "boolean",
                    "required": False,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
            ],
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_static_task_attachment_fields_catalog(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "task_attachment"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["entity_type"], "task_attachment")
        self.assertEqual(
            response.json()["items"],
            [
                {
                    "id": "TASK_ID",
                    "title": "Task ID",
                    "type": "integer",
                    "required": True,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "FILE_URL",
                    "title": "File URL",
                    "type": "string",
                    "required": True,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "FILE_NAME",
                    "title": "File name",
                    "type": "string",
                    "required": False,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
            ],
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_requires_entity_type(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(),
        )

        response = self.client.get(
            reverse("importer:fields"),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "entity_type is required")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_combined_field_catalog_for_linked_company_contact_import(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                crm=SimpleNamespace(
                    company=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "TITLE": {
                                    "title": "Название компании",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "PHONE": {
                                    "title": "Телефон компании",
                                    "type": "phone",
                                    "isRequired": False,
                                    "isMultiple": True,
                                },
                            }
                        )
                    ),
                    contact=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "NAME": {
                                    "title": "Имя контакта",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "EMAIL": {
                                    "title": "Email контакта",
                                    "type": "email",
                                    "isRequired": False,
                                    "isMultiple": True,
                                },
                            }
                        )
                    ),
                )
            ),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "linked_company_contact"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["entity_type"], "linked_company_contact")
        items_by_id = {
            item["id"]: item
            for item in response.json()["items"]
        }
        self.assertEqual(
            items_by_id["COMPANY__TITLE"],
            {
                "id": "COMPANY__TITLE",
                "title": "Компания / Название компании",
                "type": "string",
                "required": True,
                "multiple": False,
                "is_custom": False,
                "items": [],
                "linked_entity": "company",
                "linked_source_id": "TITLE",
            },
        )
        self.assertEqual(
            items_by_id["CONTACT__NAME"],
            {
                "id": "CONTACT__NAME",
                "title": "Контакт / Имя контакта",
                "type": "string",
                "required": False,
                "multiple": False,
                "is_custom": False,
                "items": [],
                "linked_entity": "contact",
                "linked_source_id": "NAME",
            },
        )
        self.assertEqual(
            items_by_id["CONTACT__EMAIL"],
            {
                "id": "CONTACT__EMAIL",
                "title": "Контакт / Email контакта",
                "type": "email",
                "required": False,
                "multiple": True,
                "is_custom": False,
                "items": [],
                "linked_entity": "contact",
                "linked_source_id": "EMAIL",
            },
        )
