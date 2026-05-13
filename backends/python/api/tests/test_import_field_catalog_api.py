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
    def test_returns_static_crm_note_fields_catalog(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "crm_note"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["entity_type"], "crm_note")

        items = response.json()["items"]
        entity_type_field = next(item for item in items if item["id"] == "ENTITY_TYPE")
        created_time_field = next(item for item in items if item["id"] == "CREATED_TIME")

        self.assertEqual(
            entity_type_field["items"],
            [
                {"id": "lead", "title": "Лид"},
                {"id": "contact", "title": "Контакт"},
                {"id": "company", "title": "Компания"},
                {"id": "deal", "title": "Сделка"},
            ],
        )
        self.assertEqual(created_time_field["title"], "Дата создания")
        self.assertEqual(created_time_field["type"], "datetime")

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

    @patch("importer.services.b24_fields.BitrixAPIRequest")
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_smart_process_fields_catalog_for_selected_entity_type_id(self, get_from_jwt_token, bitrix_api_request):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(),
        )
        bitrix_api_request.side_effect = [
            SimpleNamespace(
                result={
                    "id": {
                        "title": "ID",
                        "type": "integer",
                        "isRequired": False,
                        "isReadOnly": True,
                    },
                    "title": {
                        "title": "Название",
                        "type": "string",
                        "isRequired": True,
                        "isReadOnly": False,
                        "upperName": "TITLE",
                    },
                    "stageId": {
                        "title": "Стадия",
                        "type": "crm_status",
                        "isRequired": False,
                        "isReadOnly": False,
                        "upperName": "STAGE_ID",
                    },
                    "ufCrmSmartFlag": {
                        "title": "Кастомный флаг",
                        "type": "boolean",
                        "isRequired": False,
                        "isReadOnly": False,
                        "upperName": "UF_CRM_SMART_FLAG",
                    },
                }
            ),
            SimpleNamespace(result=[]),
        ]

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "smart_process", "entity_type_id": "128"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["entity_type"], "smart_process")
        self.assertEqual(response.json()["entity_config"], {"entityTypeId": 128})
        self.assertEqual(
            response.json()["items"],
            [
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
                    "required": False,
                    "multiple": False,
                    "is_custom": False,
                    "items": [],
                },
                {
                    "id": "ufCrmSmartFlag",
                    "title": "Кастомный флаг",
                    "type": "boolean",
                    "required": False,
                    "multiple": False,
                    "is_custom": True,
                    "items": [],
                },
            ],
        )
        self.assertEqual(
            [call.kwargs for call in bitrix_api_request.call_args_list],
            [
                {
                    "bitrix_token": get_from_jwt_token.return_value,
                    "api_method": "crm.item.fields",
                    "params": {"entityTypeId": 128},
                },
                {
                    "bitrix_token": get_from_jwt_token.return_value,
                    "api_method": "crm.status.list",
                    "params": {"filter": {"ENTITY_ID": "DYNAMIC_128_STAGE"}},
                },
            ],
        )

    @patch("importer.services.b24_fields.BitrixAPIRequest")
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_smart_process_stage_and_category_items(self, get_from_jwt_token, bitrix_api_request):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(),
        )
        bitrix_api_request.side_effect = [
            SimpleNamespace(
                result={
                    "title": {
                        "title": "Название",
                        "type": "string",
                        "isRequired": True,
                        "isReadOnly": False,
                        "upperName": "TITLE",
                    },
                    "categoryId": {
                        "title": "Воронка",
                        "type": "crm_category",
                        "isRequired": False,
                        "isReadOnly": False,
                        "upperName": "CATEGORY_ID",
                    },
                    "stageId": {
                        "title": "Стадия",
                        "type": "crm_status",
                        "isRequired": False,
                        "isReadOnly": False,
                        "upperName": "STAGE_ID",
                    },
                }
            ),
            SimpleNamespace(
                result={
                    "categories": [
                        {"id": 0, "name": "Основная"},
                        {"id": 7, "name": "Повторные продажи"},
                    ]
                }
            ),
            SimpleNamespace(
                result=[
                    {
                        "ENTITY_ID": "DYNAMIC_128_STAGE_0",
                        "STATUS_ID": "DT128_0:NEW",
                        "NAME": "Новая",
                    },
                ]
            ),
            SimpleNamespace(
                result=[
                    {
                        "ENTITY_ID": "DYNAMIC_128_STAGE_7",
                        "STATUS_ID": "DT128_7:PREPARE",
                        "NAME": "Подготовка",
                    },
                ]
            ),
        ]

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "smart_process", "entity_type_id": "128"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.content)
        items_by_id = {
            item["id"]: item
            for item in response.json()["items"]
        }
        self.assertEqual(
            items_by_id["categoryId"]["items"],
            [
                {"id": "0", "title": "Основная"},
                {"id": "7", "title": "Повторные продажи"},
            ],
        )
        self.assertEqual(
            items_by_id["stageId"]["items"],
            [
                {"id": "DT128_0:NEW", "title": "Новая"},
                {"id": "DT128_7:PREPARE", "title": "Подготовка"},
            ],
        )
        self.assertEqual(
            [call.kwargs for call in bitrix_api_request.call_args_list],
            [
                {
                    "bitrix_token": get_from_jwt_token.return_value,
                    "api_method": "crm.item.fields",
                    "params": {"entityTypeId": 128},
                },
                {
                    "bitrix_token": get_from_jwt_token.return_value,
                    "api_method": "crm.category.list",
                    "params": {"entityTypeId": 128},
                },
                {
                    "bitrix_token": get_from_jwt_token.return_value,
                    "api_method": "crm.status.list",
                    "params": {"filter": {"ENTITY_ID": "DYNAMIC_128_STAGE_0"}},
                },
                {
                    "bitrix_token": get_from_jwt_token.return_value,
                    "api_method": "crm.status.list",
                    "params": {"filter": {"ENTITY_ID": "DYNAMIC_128_STAGE_7"}},
                },
            ],
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_smart_process_fields_require_entity_type_id(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "smart_process"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "entity_type_id is required for smart_process")

    @patch("importer.services.b24_fields.BitrixAPIRequest")
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_smart_process_fields_catalog_when_bitrix_wraps_fields_key(self, get_from_jwt_token, bitrix_api_request):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(),
        )
        bitrix_api_request.side_effect = [
            SimpleNamespace(
                result={
                    "fields": {
                        "id": {
                            "title": "ID",
                            "type": "integer",
                            "isRequired": False,
                            "isReadOnly": True,
                        },
                        "title": {
                            "title": "Название",
                            "type": "string",
                            "isRequired": True,
                            "isReadOnly": False,
                            "upperName": "TITLE",
                        },
                        "stageId": {
                            "title": "Стадия",
                            "type": "crm_status",
                            "isRequired": True,
                            "isReadOnly": False,
                            "upperName": "STAGE_ID",
                        },
                    }
                }
            ),
            SimpleNamespace(
                result={
                    "categories": []
                }
            ),
            SimpleNamespace(
                result={
                    "statuses": [
                        {
                            "ENTITY_ID": "DYNAMIC_128_STAGE_0",
                            "STATUS_ID": "DT128_0:NEW",
                            "NAME": "Новая",
                        },
                    ]
                }
            ),
        ]

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "smart_process", "entity_type_id": "128"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json()["items"],
            [
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
                    "items": [
                        {"id": "DT128_0:NEW", "title": "Новая"},
                    ],
                },
            ],
        )
