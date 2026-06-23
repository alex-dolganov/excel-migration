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
    def test_filters_out_readonly_and_system_uf_fields_from_deal_catalog(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                crm=SimpleNamespace(
                    deal=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "TITLE": {"title": "Deal title", "type": "string", "isRequired": False},
                                "ID": {"title": "ID", "type": "integer", "isReadOnly": True},
                                "DATE_CREATE": {"title": "Created", "type": "datetime", "isReadOnly": True},
                                "UF_CRM_KASSA_ORDER_CRC": {"title": "KASSA crc", "type": "string"},
                                "UF_CRM_PAYMENT_AMOUNT": {"title": "Payment", "type": "money"},
                                "UF_CRM_CUSTOM_FIELD": {"title": "My field", "type": "string"},
                            }
                        )
                    )
                )
            ),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "deal"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()["items"]]
        self.assertIn("TITLE", ids)
        self.assertIn("UF_CRM_CUSTOM_FIELD", ids)
        self.assertNotIn("ID", ids)
        self.assertNotIn("DATE_CREATE", ids)
        self.assertNotIn("UF_CRM_KASSA_ORDER_CRC", ids)
        self.assertNotIn("UF_CRM_PAYMENT_AMOUNT", ids)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_prefers_bitrix_userfield_labels_over_uf_crm_code(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                crm=SimpleNamespace(
                    deal=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "UF_CRM_CUSTOM_PROMO": {
                                    "title": "UF_CRM_CUSTOM_PROMO",
                                    "formLabel": "UF_CRM_CUSTOM_PROMO",
                                    "editFormLabel": "Промо-материалы",
                                    "listColumnLabel": "Промо-материалы",
                                    "type": "file",
                                    "isRequired": False,
                                    "isMultiple": True,
                                },
                            }
                        )
                    )
                )
            ),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "deal"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["items"],
            [
                {
                    "id": "UF_CRM_CUSTOM_PROMO",
                    "title": "Промо-материалы",
                    "type": "file",
                    "required": False,
                    "multiple": True,
                    "is_custom": True,
                    "items": [],
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
    def test_returns_task_fields_catalog_with_custom_fields_from_bitrix(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                tasks=SimpleNamespace(
                    task=SimpleNamespace(
                        getFields=lambda: FakeFieldsRequest(
                            {
                                "TITLE": {
                                    "title": "Название задачи",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "DEADLINE": {
                                    "title": "Крайний срок",
                                    "type": "datetime",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                                "UF_AUTO_155439530230": {
                                    "title": "UF_AUTO_155439530230",
                                    "formLabel": "UF_AUTO_155439530230",
                                    "editFormLabel": "Код проекта",
                                    "type": "string",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                                "UF_AUTO_155439530231": {
                                    "title": "Стадия задачи",
                                    "type": "enumeration",
                                    "isRequired": False,
                                    "isMultiple": True,
                                    "items": {
                                        "32": "Новая",
                                        "33": "В работе",
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
            data={"entity_type": "task"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["entity_type"], "task")
        items_by_id = {
            item["id"]: item
            for item in response.json()["items"]
        }

        self.assertIn("DESCRIPTION", items_by_id)
        self.assertIn("RESPONSIBLE_ID", items_by_id)
        self.assertEqual(
            items_by_id["TITLE"],
            {
                "id": "TITLE",
                "title": "Название задачи",
                "type": "string",
                "required": True,
                "multiple": False,
                "is_custom": False,
                "items": [],
            },
        )
        self.assertEqual(
            items_by_id["DEADLINE"],
            {
                "id": "DEADLINE",
                "title": "Крайний срок",
                "type": "datetime",
                "required": False,
                "multiple": False,
                "is_custom": False,
                "items": [],
            },
        )
        self.assertEqual(
            items_by_id["UF_AUTO_155439530230"],
            {
                "id": "UF_AUTO_155439530230",
                "title": "Код проекта",
                "type": "string",
                "required": False,
                "multiple": False,
                "is_custom": True,
                "items": [],
            },
        )
        self.assertEqual(
            items_by_id["UF_AUTO_155439530231"],
            {
                "id": "UF_AUTO_155439530231",
                "title": "Стадия задачи",
                "type": "enumeration",
                "required": False,
                "multiple": True,
                "is_custom": True,
                "items": [
                    {"id": "32", "title": "Новая"},
                    {"id": "33", "title": "В работе"},
                ],
            },
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_task_fields_catalog_falls_back_to_static_fields_when_bitrix_loader_is_unavailable(self, get_from_jwt_token):
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
        items_by_id = {
            item["id"]: item
            for item in response.json()["items"]
        }
        self.assertEqual(
            items_by_id["TITLE"],
            {
                "id": "TITLE",
                "title": "Название задачи",
                "type": "string",
                "required": True,
                "multiple": False,
                "is_custom": False,
                "items": [],
            },
        )
        self.assertEqual(
            items_by_id["DESCRIPTION"],
            {
                "id": "DESCRIPTION",
                "title": "Описание",
                "type": "text",
                "required": False,
                "multiple": False,
                "is_custom": False,
                "items": [],
            },
        )
        self.assertEqual(
            items_by_id["RESPONSIBLE_ID"],
            {
                "id": "RESPONSIBLE_ID",
                "title": "Ответственный (ID)",
                "type": "integer",
                "required": True,
                "multiple": False,
                "is_custom": False,
                "items": [],
            },
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_task_fields_catalog_when_bitrix_wraps_fields_key(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                tasks=SimpleNamespace(
                    task=SimpleNamespace(
                        getFields=lambda: FakeFieldsRequest(
                            {
                                "fields": {
                                    "TITLE": {
                                        "title": "Название",
                                        "type": "string",
                                        "required": True,
                                    },
                                    "UF_AUTO_100500": {
                                        "title": "UF_AUTO_100500",
                                        "editFormLabel": {"ru": "Новое строковое поле"},
                                        "type": "string",
                                        "required": False,
                                    },
                                }
                            }
                        )
                    )
                )
            ),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "task"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.content)
        items_by_id = {
            item["id"]: item
            for item in response.json()["items"]
        }

        self.assertEqual(items_by_id["TITLE"]["title"], "Название")
        self.assertEqual(items_by_id["UF_AUTO_100500"]["title"], "Новое строковое поле")
        self.assertEqual(items_by_id["UF_AUTO_100500"]["type"], "string")
        self.assertEqual(items_by_id["UF_AUTO_100500"]["is_custom"], True)

    @patch("importer.services.b24_fields.BitrixAPIRequest")
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_merges_task_custom_fields_from_userfield_api_when_getfields_omits_them(self, get_from_jwt_token, bitrix_api_request):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                tasks=SimpleNamespace(
                    task=SimpleNamespace(
                        getFields=lambda: FakeFieldsRequest(
                            {
                                "fields": {
                                    "TITLE": {
                                        "title": "Название",
                                        "type": "string",
                                        "required": True,
                                    },
                                    "DESCRIPTION": {
                                        "title": "Описание",
                                        "type": "string",
                                    },
                                }
                            }
                        )
                    )
                )
            ),
        )
        bitrix_api_request.side_effect = [
            SimpleNamespace(
                result=[
                    {
                        "ID": "1325",
                        "FIELD_NAME": "UF_TASK_CLIENT_REQUEST",
                        "USER_TYPE_ID": "string",
                        "MULTIPLE": "N",
                        "MANDATORY": "N",
                    },
                    {
                        "ID": "1327",
                        "FIELD_NAME": "UF_TASK_PIPELINE_STAGE",
                        "USER_TYPE_ID": "enumeration",
                        "MULTIPLE": "Y",
                        "MANDATORY": "N",
                    },
                ]
            ),
            SimpleNamespace(
                result={
                    "ID": "1325",
                    "FIELD_NAME": "UF_TASK_CLIENT_REQUEST",
                    "USER_TYPE_ID": "string",
                    "MULTIPLE": "N",
                    "MANDATORY": "N",
                    "EDIT_FORM_LABEL": {"ru": "Новое строковое поле"},
                }
            ),
            SimpleNamespace(
                result={
                    "ID": "1327",
                    "FIELD_NAME": "UF_TASK_PIPELINE_STAGE",
                    "USER_TYPE_ID": "enumeration",
                    "MULTIPLE": "Y",
                    "MANDATORY": "N",
                    "EDIT_FORM_LABEL": {"ru": "Этап задачи"},
                    "SETTINGS": {
                        "LIST": [
                            {"ID": "32", "VALUE": "Новая"},
                            {"ID": "33", "VALUE": "В работе"},
                        ]
                    },
                }
            ),
        ]

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "task"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.content)
        items_by_id = {
            item["id"]: item
            for item in response.json()["items"]
        }

        self.assertEqual(items_by_id["UF_TASK_CLIENT_REQUEST"]["title"], "Новое строковое поле")
        self.assertEqual(items_by_id["UF_TASK_CLIENT_REQUEST"]["type"], "string")
        self.assertEqual(items_by_id["UF_TASK_CLIENT_REQUEST"]["is_custom"], True)
        self.assertEqual(items_by_id["UF_TASK_PIPELINE_STAGE"]["title"], "Этап задачи")
        self.assertEqual(items_by_id["UF_TASK_PIPELINE_STAGE"]["type"], "enumeration")
        self.assertEqual(
            items_by_id["UF_TASK_PIPELINE_STAGE"]["items"],
            [
                {"id": "32", "title": "Новая"},
                {"id": "33", "title": "В работе"},
            ],
        )
        self.assertEqual(
            [call.kwargs for call in bitrix_api_request.call_args_list],
            [
                {
                    "bitrix_token": get_from_jwt_token.return_value,
                    "api_method": "task.item.userfield.getlist",
                    "params": {"ORDER": {"SORT": "ASC"}},
                },
                {
                    "bitrix_token": get_from_jwt_token.return_value,
                    "api_method": "task.item.userfield.get",
                    "params": {"ID": 1325},
                },
                {
                    "bitrix_token": get_from_jwt_token.return_value,
                    "api_method": "task.item.userfield.get",
                    "params": {"ID": 1327},
                },
            ],
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_filters_out_internal_task_fields_from_bitrix_catalog(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                tasks=SimpleNamespace(
                    task=SimpleNamespace(
                        getFields=lambda: FakeFieldsRequest(
                            {
                                "fields": {
                                    "TITLE": {
                                        "title": "Title",
                                        "type": "string",
                                        "required": True,
                                    },
                                    "RESPONSIBLE_ID": {
                                        "title": "Responsible",
                                        "type": "integer",
                                        "required": True,
                                    },
                                    "isPinned": {
                                        "title": "Is pinned",
                                        "type": "boolean",
                                    },
                                    "notViewed": {
                                        "title": "Not viewed",
                                        "type": "boolean",
                                    },
                                    "UF_TASK_CLIENT_REQUEST": {
                                        "title": "UF_TASK_CLIENT_REQUEST",
                                        "editFormLabel": {"ru": "Новое строковое поле"},
                                        "type": "string",
                                    },
                                }
                            }
                        )
                    )
                )
            ),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "task"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.content)
        items_by_id = {
            item["id"]: item
            for item in response.json()["items"]
        }

        self.assertIn("TITLE", items_by_id)
        self.assertIn("RESPONSIBLE_ID", items_by_id)
        self.assertIn("UF_TASK_CLIENT_REQUEST", items_by_id)
        self.assertNotIn("isPinned", items_by_id)
        self.assertNotIn("notViewed", items_by_id)

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
    def test_normalizes_company_utm_field_titles_for_mapping_search(self, get_from_jwt_token):
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
                                "UTM_SOURCE": {
                                    "title": "UTM_SOURCE",
                                    "type": "string",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                                "UTM_MEDIUM": {
                                    "title": "UTM_MEDIUM",
                                    "type": "string",
                                    "isRequired": False,
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
            data={"entity_type": "company"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.content)
        items_by_id = {
            item["id"]: item
            for item in response.json()["items"]
        }
        self.assertEqual(items_by_id["UTM_SOURCE"]["title"], "Сквозная аналитика: источник")
        self.assertEqual(items_by_id["UTM_MEDIUM"]["title"], "Сквозная аналитика: тип трафика")

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
        self.assertEqual(
            response.json()["linked_entities"],
            [
                {
                    "id": "company",
                    "label": "Компания",
                    "source_entity_type": "company",
                    "prefix": "COMPANY__",
                    "excluded_source_ids": [],
                },
                {
                    "id": "contact",
                    "label": "Контакт",
                    "source_entity_type": "contact",
                    "prefix": "CONTACT__",
                    "excluded_source_ids": ["COMPANY_ID"],
                },
            ],
        )
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

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_combined_field_catalog_for_linked_company_deal_import(self, get_from_jwt_token):
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
                    deal=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "TITLE": {
                                    "title": "Название сделки",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "OPPORTUNITY": {
                                    "title": "Сумма",
                                    "type": "money",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                                "COMPANY_ID": {
                                    "title": "Компания",
                                    "type": "integer",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                            }
                        )
                    ),
                )
            ),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "linked_company_deal"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["entity_type"], "linked_company_deal")
        self.assertEqual(
            response.json()["linked_entities"],
            [
                {
                    "id": "company",
                    "label": "Компания",
                    "source_entity_type": "company",
                    "prefix": "COMPANY__",
                    "excluded_source_ids": [],
                },
                {
                    "id": "deal",
                    "label": "Сделка",
                    "source_entity_type": "deal",
                    "prefix": "DEAL__",
                    "excluded_source_ids": ["COMPANY_ID"],
                },
            ],
        )
        items_by_id = {
            item["id"]: item
            for item in response.json()["items"]
        }
        self.assertEqual(items_by_id["COMPANY__TITLE"]["title"], "Компания / Название компании")
        self.assertEqual(items_by_id["DEAL__TITLE"]["title"], "Сделка / Название сделки")
        self.assertEqual(items_by_id["DEAL__OPPORTUNITY"]["title"], "Сделка / Сумма")
        self.assertNotIn("DEAL__COMPANY_ID", items_by_id)

    @patch("importer.services.b24_fields.BitrixAPIRequest")
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_deal_stage_items_for_linked_company_deal_when_raw_catalog_is_empty(self, get_from_jwt_token, bitrix_api_request):
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
                            }
                        )
                    ),
                    deal=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "TITLE": {
                                    "title": "Название сделки",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "STAGE_ID": {
                                    "title": "Стадия сделки",
                                    "type": "crm_status",
                                    "isRequired": False,
                                    "isMultiple": False,
                                    "items": [],
                                },
                                "COMPANY_ID": {
                                    "title": "Компания",
                                    "type": "integer",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                            }
                        )
                    ),
                )
            ),
        )
        bitrix_api_request.return_value = SimpleNamespace(
            result={
                "statuses": [
                    {"STATUS_ID": "NEW", "NAME": "Новая"},
                    {"STATUS_ID": "IN_PROGRESS", "NAME": "В работе"},
                ]
            }
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "linked_company_deal"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.content)
        items_by_id = {item["id"]: item for item in response.json()["items"]}
        self.assertEqual(
            items_by_id["DEAL__STAGE_ID"]["items"],
            [
                {"id": "NEW", "title": "Новая"},
                {"id": "IN_PROGRESS", "title": "В работе"},
            ],
        )
        self.assertEqual(
            [call.kwargs for call in bitrix_api_request.call_args_list],
            [
                {
                    "bitrix_token": get_from_jwt_token.return_value,
                    "api_method": "crm.status.list",
                    "params": {"filter": {"ENTITY_ID": "DEAL_STAGE"}},
                },
            ],
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_combined_field_catalog_for_linked_contact_deal_import_with_custom_fields(self, get_from_jwt_token):
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
                                "UF_CRM_CONTACT_SOURCE": {
                                    "title": "Источник контакта",
                                    "type": "string",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                            }
                        )
                    ),
                    deal=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "TITLE": {
                                    "title": "Название сделки",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "OPPORTUNITY": {
                                    "title": "Сумма",
                                    "type": "money",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                                "CONTACT_ID": {
                                    "title": "Контакт",
                                    "type": "integer",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                                "UF_CRM_DEAL_CHANNEL": {
                                    "title": "Канал сделки",
                                    "type": "string",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                            }
                        )
                    ),
                )
            ),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "linked_contact_deal"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["entity_type"], "linked_contact_deal")
        self.assertEqual(
            response.json()["linked_entities"],
            [
                {
                    "id": "contact",
                    "label": "Контакт",
                    "source_entity_type": "contact",
                    "prefix": "CONTACT__",
                    "excluded_source_ids": [],
                },
                {
                    "id": "deal",
                    "label": "Сделка",
                    "source_entity_type": "deal",
                    "prefix": "DEAL__",
                    "excluded_source_ids": ["CONTACT_ID"],
                },
            ],
        )
        items_by_id = {
            item["id"]: item
            for item in response.json()["items"]
        }
        self.assertEqual(items_by_id["CONTACT__NAME"]["title"], "Контакт / Имя контакта")
        self.assertEqual(items_by_id["DEAL__TITLE"]["title"], "Сделка / Название сделки")
        self.assertEqual(
            items_by_id["CONTACT__UF_CRM_CONTACT_SOURCE"],
            {
                "id": "CONTACT__UF_CRM_CONTACT_SOURCE",
                "title": "Контакт / Источник контакта",
                "type": "string",
                "required": False,
                "multiple": False,
                "is_custom": True,
                "items": [],
                "linked_entity": "contact",
                "linked_source_id": "UF_CRM_CONTACT_SOURCE",
            },
        )
        self.assertEqual(
            items_by_id["DEAL__UF_CRM_DEAL_CHANNEL"],
            {
                "id": "DEAL__UF_CRM_DEAL_CHANNEL",
                "title": "Сделка / Канал сделки",
                "type": "string",
                "required": False,
                "multiple": False,
                "is_custom": True,
                "items": [],
                "linked_entity": "deal",
                "linked_source_id": "UF_CRM_DEAL_CHANNEL",
            },
        )
        self.assertNotIn("DEAL__CONTACT_ID", items_by_id)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_combined_field_catalog_for_linked_contact_company_import_with_custom_fields(self, get_from_jwt_token):
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
                                "COMPANY_ID": {
                                    "title": "Компания",
                                    "type": "integer",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                                "UF_CRM_CONTACT_SOURCE": {
                                    "title": "Источник контакта",
                                    "type": "string",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                            }
                        )
                    ),
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
                                "UF_CRM_COMPANY_SEGMENT": {
                                    "title": "Сегмент компании",
                                    "type": "string",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                            }
                        )
                    ),
                )
            ),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "linked_contact_company"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["entity_type"], "linked_contact_company")
        self.assertEqual(
            response.json()["linked_entities"],
            [
                {
                    "id": "contact",
                    "label": "Контакт",
                    "source_entity_type": "contact",
                    "prefix": "CONTACT__",
                    "excluded_source_ids": ["COMPANY_ID"],
                },
                {
                    "id": "company",
                    "label": "Компания",
                    "source_entity_type": "company",
                    "prefix": "COMPANY__",
                    "excluded_source_ids": [],
                },
            ],
        )
        items_by_id = {item["id"]: item for item in response.json()["items"]}
        self.assertEqual(items_by_id["CONTACT__EXTERNAL_KEY"]["title"], "Контакт / Внешний ключ (XML_ID)")
        self.assertEqual(items_by_id["CONTACT__NAME"]["title"], "Контакт / Имя контакта")
        self.assertEqual(items_by_id["COMPANY__TITLE"]["title"], "Компания / Название компании")
        self.assertEqual(items_by_id["COMPANY__UF_CRM_COMPANY_SEGMENT"]["title"], "Компания / Сегмент компании")
        self.assertNotIn("CONTACT__COMPANY_ID", items_by_id)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_combined_field_catalog_for_linked_deal_contact_import_with_custom_fields(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                crm=SimpleNamespace(
                    deal=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "TITLE": {
                                    "title": "Название сделки",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "OPPORTUNITY": {
                                    "title": "Сумма",
                                    "type": "money",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                                "CONTACT_ID": {
                                    "title": "Контакт",
                                    "type": "integer",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                                "UF_CRM_DEAL_CHANNEL": {
                                    "title": "Канал сделки",
                                    "type": "string",
                                    "isRequired": False,
                                    "isMultiple": False,
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
                                "UF_CRM_CONTACT_SOURCE": {
                                    "title": "Источник контакта",
                                    "type": "string",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                            }
                        )
                    ),
                )
            ),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "linked_deal_contact"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["entity_type"], "linked_deal_contact")
        self.assertEqual(
            response.json()["linked_entities"],
            [
                {
                    "id": "deal",
                    "label": "Сделка",
                    "source_entity_type": "deal",
                    "prefix": "DEAL__",
                    "excluded_source_ids": ["CONTACT_ID"],
                },
                {
                    "id": "contact",
                    "label": "Контакт",
                    "source_entity_type": "contact",
                    "prefix": "CONTACT__",
                    "excluded_source_ids": [],
                },
            ],
        )
        items_by_id = {
            item["id"]: item
            for item in response.json()["items"]
        }
        self.assertEqual(items_by_id["DEAL__EXTERNAL_KEY"]["title"], "Сделка / Внешний ключ (XML_ID)")
        self.assertEqual(items_by_id["DEAL__TITLE"]["title"], "Сделка / Название сделки")
        self.assertEqual(items_by_id["CONTACT__NAME"]["title"], "Контакт / Имя контакта")
        self.assertEqual(
            items_by_id["CONTACT__UF_CRM_CONTACT_SOURCE"],
            {
                "id": "CONTACT__UF_CRM_CONTACT_SOURCE",
                "title": "Контакт / Источник контакта",
                "type": "string",
                "required": False,
                "multiple": False,
                "is_custom": True,
                "items": [],
                "linked_entity": "contact",
                "linked_source_id": "UF_CRM_CONTACT_SOURCE",
            },
        )
        self.assertNotIn("DEAL__CONTACT_ID", items_by_id)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_combined_field_catalog_for_linked_deal_company_import_with_custom_fields(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                crm=SimpleNamespace(
                    deal=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "TITLE": {
                                    "title": "Название сделки",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "COMPANY_ID": {
                                    "title": "Компания",
                                    "type": "integer",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                                "UF_CRM_DEAL_CHANNEL": {
                                    "title": "Канал сделки",
                                    "type": "string",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                            }
                        )
                    ),
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
                                "UF_CRM_COMPANY_SEGMENT": {
                                    "title": "Сегмент компании",
                                    "type": "string",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                            }
                        )
                    ),
                )
            ),
        )

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "linked_deal_company"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["entity_type"], "linked_deal_company")
        self.assertEqual(
            response.json()["linked_entities"],
            [
                {
                    "id": "deal",
                    "label": "Сделка",
                    "source_entity_type": "deal",
                    "prefix": "DEAL__",
                    "excluded_source_ids": ["COMPANY_ID"],
                },
                {
                    "id": "company",
                    "label": "Компания",
                    "source_entity_type": "company",
                    "prefix": "COMPANY__",
                    "excluded_source_ids": [],
                },
            ],
        )
        items_by_id = {item["id"]: item for item in response.json()["items"]}
        self.assertEqual(items_by_id["DEAL__EXTERNAL_KEY"]["title"], "Сделка / Внешний ключ (XML_ID)")
        self.assertEqual(items_by_id["DEAL__TITLE"]["title"], "Сделка / Название сделки")
        self.assertEqual(items_by_id["COMPANY__TITLE"]["title"], "Компания / Название компании")
        self.assertEqual(items_by_id["COMPANY__UF_CRM_COMPANY_SEGMENT"]["title"], "Компания / Сегмент компании")
        self.assertNotIn("DEAL__COMPANY_ID", items_by_id)

    @patch("importer.services.b24_fields.BitrixAPIRequest")
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_deal_crm_status_items_from_crm_status_list_when_field_catalog_is_empty(self, get_from_jwt_token, bitrix_api_request):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                crm=SimpleNamespace(
                    deal=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "TITLE": {
                                    "title": "Название",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "SOURCE_ID": {
                                    "title": "Источник",
                                    "type": "crm_status",
                                    "isRequired": False,
                                    "isMultiple": False,
                                    "items": [],
                                },
                                "TYPE_ID": {
                                    "title": "Тип",
                                    "type": "crm_status",
                                    "isRequired": False,
                                    "isMultiple": False,
                                    "items": [],
                                },
                                "STAGE_ID": {
                                    "title": "Стадия сделки",
                                    "type": "crm_status",
                                    "isRequired": False,
                                    "isMultiple": False,
                                    "items": [],
                                },
                            }
                        )
                    )
                )
            ),
        )
        statuses_by_entity_id = {
            "SOURCE": [
                {"STATUS_ID": "ADVERTISING", "NAME": "Реклама"},
                {"STATUS_ID": "WEB", "NAME": "Сайт"},
            ],
            "DEAL_TYPE": [
                {"STATUS_ID": "SALE", "NAME": "Продажа"},
            ],
            "DEAL_STAGE": [
                {"STATUS_ID": "NEW", "NAME": "Новая"},
            ],
        }

        def build_status_response(*args, **kwargs):
            entity_id = kwargs["params"]["filter"]["ENTITY_ID"]
            return SimpleNamespace(result={"statuses": statuses_by_entity_id[entity_id]})

        bitrix_api_request.side_effect = build_status_response

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "deal"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.content)
        items_by_id = {
            item["id"]: item
            for item in response.json()["items"]
        }
        self.assertEqual(
            items_by_id["SOURCE_ID"]["items"],
            [
                {"id": "ADVERTISING", "title": "Реклама"},
                {"id": "WEB", "title": "Сайт"},
            ],
        )
        self.assertEqual(
            items_by_id["TYPE_ID"]["items"],
            [
                {"id": "SALE", "title": "Продажа"},
            ],
        )
        self.assertEqual(
            items_by_id["STAGE_ID"]["items"],
            [
                {"id": "NEW", "title": "Новая"},
            ],
        )
        self.assertEqual(
            [call.kwargs for call in bitrix_api_request.call_args_list],
            [
                {
                    "bitrix_token": get_from_jwt_token.return_value,
                    "api_method": "crm.status.list",
                    "params": {"filter": {"ENTITY_ID": "SOURCE"}},
                },
                {
                    "bitrix_token": get_from_jwt_token.return_value,
                    "api_method": "crm.status.list",
                    "params": {"filter": {"ENTITY_ID": "DEAL_STAGE"}},
                },
                {
                    "bitrix_token": get_from_jwt_token.return_value,
                    "api_method": "crm.status.list",
                    "params": {"filter": {"ENTITY_ID": "DEAL_TYPE"}},
                },
            ],
        )

    @patch("importer.services.b24_fields.BitrixAPIRequest")
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_deal_category_and_currency_items_for_enum_filters(self, get_from_jwt_token, bitrix_api_request):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                crm=SimpleNamespace(
                    deal=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "TITLE": {
                                    "title": "Название",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "CATEGORY_ID": {
                                    "title": "Воронка",
                                    "type": "crm_category",
                                    "isRequired": False,
                                    "isMultiple": False,
                                    "items": [],
                                },
                                "CURRENCY_ID": {
                                    "title": "Валюта",
                                    "type": "crm_currency",
                                    "isRequired": False,
                                    "isMultiple": False,
                                    "items": [],
                                },
                            }
                        )
                    )
                )
            ),
        )

        def build_lookup_response(*args, **kwargs):
            api_method = kwargs["api_method"]
            if api_method == "crm.category.list":
                return SimpleNamespace(
                    result={
                        "categories": [
                            {"ID": 0, "NAME": "Общая"},
                            {"ID": 7, "NAME": "Повторные продажи"},
                        ]
                    }
                )

            if api_method == "crm.currency.list":
                return SimpleNamespace(
                    result={
                        "result": [
                            {"CURRENCY": "RUB", "FULL_NAME": "Российский рубль"},
                            {"CURRENCY": "USD", "FULL_NAME": "Доллар США"},
                        ]
                    }
                )

            raise AssertionError(f"Unexpected Bitrix API method: {api_method}")

        bitrix_api_request.side_effect = build_lookup_response

        response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "deal"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.content)
        items_by_id = {
            item["id"]: item
            for item in response.json()["items"]
        }
        self.assertEqual(
            items_by_id["CATEGORY_ID"]["items"],
            [
                {"id": "0", "title": "Общая"},
                {"id": "7", "title": "Повторные продажи"},
            ],
        )
        self.assertEqual(
            items_by_id["CURRENCY_ID"]["items"],
            [
                {"id": "RUB", "title": "Российский рубль"},
                {"id": "USD", "title": "Доллар США"},
            ],
        )
        self.assertCountEqual(
            [call.kwargs for call in bitrix_api_request.call_args_list],
            [
                {
                    "bitrix_token": get_from_jwt_token.return_value,
                    "api_method": "crm.category.list",
                    "params": {"entityTypeId": 2},
                },
                {
                    "bitrix_token": get_from_jwt_token.return_value,
                    "api_method": "crm.currency.list",
                    "params": {},
                },
            ],
        )

    @patch("importer.services.b24_fields.BitrixAPIRequest")
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_standard_crm_status_items_for_leads_contacts_and_companies_when_field_catalog_is_empty(self, get_from_jwt_token, bitrix_api_request):
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
                                    "title": "Название",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "SOURCE_ID": {
                                    "title": "Источник",
                                    "type": "crm_status",
                                    "items": [],
                                },
                                "HONORIFIC": {
                                    "title": "Обращение",
                                    "type": "crm_status",
                                    "items": [],
                                },
                                "STATUS_ID": {
                                    "title": "Стадия",
                                    "type": "crm_status",
                                    "items": [],
                                },
                            }
                        )
                    ),
                    contact=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "NAME": {
                                    "title": "Имя",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "SOURCE_ID": {
                                    "title": "Источник",
                                    "type": "crm_status",
                                    "items": [],
                                },
                                "HONORIFIC": {
                                    "title": "Обращение",
                                    "type": "crm_status",
                                    "items": [],
                                },
                                "TYPE_ID": {
                                    "title": "Тип контакта",
                                    "type": "crm_status",
                                    "items": [],
                                },
                            }
                        )
                    ),
                    company=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "TITLE": {
                                    "title": "Название компании",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "EMPLOYEES": {
                                    "title": "Кол-во сотрудников",
                                    "type": "crm_status",
                                    "items": [],
                                },
                                "INDUSTRY": {
                                    "title": "Сфера деятельности",
                                    "type": "crm_status",
                                    "items": [],
                                },
                                "COMPANY_TYPE": {
                                    "title": "Тип компании",
                                    "type": "crm_status",
                                    "items": [],
                                },
                            }
                        )
                    ),
                )
            ),
        )
        statuses_by_entity_id = {
            "SOURCE": [
                {"STATUS_ID": "ADVERTISING", "NAME": "Реклама"},
            ],
            "HONORIFIC": [
                {"STATUS_ID": "HNR_RU_1", "NAME": "г-н"},
            ],
            "STATUS": [
                {"STATUS_ID": "NEW", "NAME": "Не обработан"},
            ],
            "CONTACT_TYPE": [
                {"STATUS_ID": "CLIENT", "NAME": "Клиенты"},
            ],
            "EMPLOYEES": [
                {"STATUS_ID": "EMPLOYEES_1", "NAME": "менее 50"},
            ],
            "INDUSTRY": [
                {"STATUS_ID": "IT", "NAME": "Информационные технологии"},
            ],
            "COMPANY_TYPE": [
                {"STATUS_ID": "CUSTOMER", "NAME": "Клиент"},
            ],
        }

        def build_status_response(*args, **kwargs):
            entity_id = kwargs["params"]["filter"]["ENTITY_ID"]
            return SimpleNamespace(result={"statuses": statuses_by_entity_id[entity_id]})

        bitrix_api_request.side_effect = build_status_response

        lead_response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "lead"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        contact_response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "contact"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        company_response = self.client.get(
            reverse("importer:fields"),
            data={"entity_type": "company"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(lead_response.status_code, 200, lead_response.content)
        self.assertEqual(contact_response.status_code, 200, contact_response.content)
        self.assertEqual(company_response.status_code, 200, company_response.content)

        lead_items_by_id = {item["id"]: item for item in lead_response.json()["items"]}
        contact_items_by_id = {item["id"]: item for item in contact_response.json()["items"]}
        company_items_by_id = {item["id"]: item for item in company_response.json()["items"]}

        self.assertEqual(lead_items_by_id["SOURCE_ID"]["items"], [{"id": "ADVERTISING", "title": "Реклама"}])
        self.assertEqual(lead_items_by_id["HONORIFIC"]["items"], [{"id": "HNR_RU_1", "title": "г-н"}])
        self.assertEqual(lead_items_by_id["STATUS_ID"]["items"], [{"id": "NEW", "title": "Не обработан"}])

        self.assertEqual(contact_items_by_id["SOURCE_ID"]["items"], [{"id": "ADVERTISING", "title": "Реклама"}])
        self.assertEqual(contact_items_by_id["HONORIFIC"]["items"], [{"id": "HNR_RU_1", "title": "г-н"}])
        self.assertEqual(contact_items_by_id["TYPE_ID"]["items"], [{"id": "CLIENT", "title": "Клиенты"}])

        self.assertEqual(company_items_by_id["EMPLOYEES"]["items"], [{"id": "EMPLOYEES_1", "title": "менее 50"}])
        self.assertEqual(company_items_by_id["INDUSTRY"]["items"], [{"id": "IT", "title": "Информационные технологии"}])
        self.assertEqual(company_items_by_id["COMPANY_TYPE"]["items"], [{"id": "CUSTOMER", "title": "Клиент"}])

        requested_entity_ids = [call.kwargs["params"]["filter"]["ENTITY_ID"] for call in bitrix_api_request.call_args_list]
        self.assertCountEqual(
            requested_entity_ids,
            [
                "SOURCE",
                "HONORIFIC",
                "STATUS",
                "SOURCE",
                "HONORIFIC",
                "CONTACT_TYPE",
                "EMPLOYEES",
                "INDUSTRY",
                "COMPANY_TYPE",
            ],
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
            SimpleNamespace(result=[]),  # crm.category.list
            SimpleNamespace(result=[]),  # crm.status.list DYNAMIC_128_STAGE_0
            SimpleNamespace(result=[]),  # crm.status.list DYNAMIC_128_STAGE
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

    @patch("importer.services.b24_fields.BitrixAPIRequest")
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_smart_process_source_items_from_status_type(self, get_from_jwt_token, bitrix_api_request):
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
                    "sourceId": {
                        "title": "Источник",
                        "type": "crm_status",
                        "isRequired": False,
                        "isReadOnly": False,
                        "upperName": "SOURCE_ID",
                        "settings": {
                            "statusType": "SOURCE",
                        },
                    },
                }
            ),
            SimpleNamespace(
                result={
                    "statuses": [
                        {
                            "ENTITY_ID": "SOURCE",
                            "STATUS_ID": "OTHER",
                            "NAME": "Другое",
                        },
                        {
                            "ENTITY_ID": "SOURCE",
                            "STATUS_ID": "ADVERTISING",
                            "NAME": "Реклама",
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
        items_by_id = {
            item["id"]: item
            for item in response.json()["items"]
        }
        self.assertEqual(
            items_by_id["sourceId"]["items"],
            [
                {"id": "OTHER", "title": "Другое"},
                {"id": "ADVERTISING", "title": "Реклама"},
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
                    "params": {"filter": {"ENTITY_ID": "SOURCE"}},
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
                    "required": False,
                    "multiple": False,
                    "is_custom": False,
                    "items": [
                        {"id": "DT128_0:NEW", "title": "Новая"},
                    ],
                },
            ],
        )
