from types import SimpleNamespace

from django.test import SimpleTestCase

from unittest.mock import patch

from importer.services.import_execution import (
    build_linked_result_fields,
    build_linked_row_payload,
    build_row_payload,
    create_entity_record,
    normalize_entity_dedup_settings,
)


class FakeUsersRequest:
    def __init__(self, result):
        self.result = result


class ImportExecutionServiceTest(SimpleTestCase):
    def test_build_linked_row_payload_splits_company_and_contact_fields(self):
        payload = build_linked_row_payload(
            row=["ООО Альфа", "+78005550101", "Алиса", "Иванова", "alice@example.ru"],
            columns=["A", "B", "C", "D", "E"],
            mapping={
                "COMPANY__TITLE": {
                    "column": "A",
                    "source_header": "Название компании",
                },
                "COMPANY__PHONE": {
                    "column": "B",
                    "source_header": "Телефон компании",
                },
                "CONTACT__NAME": {
                    "column": "C",
                    "source_header": "Имя контакта",
                },
                "CONTACT__LAST_NAME": {
                    "column": "D",
                    "source_header": "Фамилия контакта",
                },
                "CONTACT__EMAIL": {
                    "column": "E",
                    "source_header": "Email контакта",
                },
            },
            fields=[
                {"id": "COMPANY__TITLE", "type": "string", "multiple": False, "linked_entity": "company", "linked_source_id": "TITLE"},
                {"id": "COMPANY__PHONE", "type": "phone", "multiple": True, "linked_entity": "company", "linked_source_id": "PHONE"},
                {"id": "CONTACT__NAME", "type": "string", "multiple": False, "linked_entity": "contact", "linked_source_id": "NAME"},
                {"id": "CONTACT__LAST_NAME", "type": "string", "multiple": False, "linked_entity": "contact", "linked_source_id": "LAST_NAME"},
                {"id": "CONTACT__EMAIL", "type": "email", "multiple": True, "linked_entity": "contact", "linked_source_id": "EMAIL"},
            ],
        )

        self.assertEqual(
            payload,
            {
                "company": {
                    "TITLE": "ООО Альфа",
                    "PHONE": [{"VALUE": "+78005550101", "VALUE_TYPE": "WORK"}],
                },
                "contact": {
                    "NAME": "Алиса",
                    "LAST_NAME": "Иванова",
                    "EMAIL": [{"VALUE": "alice@example.ru", "VALUE_TYPE": "WORK"}],
                },
            },
        )

    def test_build_linked_result_fields_flattens_payload_using_linked_schema_prefixes(self):
        self.assertEqual(
            build_linked_result_fields(
                {
                    "company": {
                        "TITLE": "ООО Альфа",
                    },
                    "contact": {
                        "NAME": "Алиса",
                        "EMAIL": [{"VALUE": "alice@example.ru", "VALUE_TYPE": "WORK"}],
                    },
                    "deal": {
                        "TITLE": "Ignored",
                    },
                }
            ),
            {
                "COMPANY__TITLE": "ООО Альфа",
                "CONTACT__NAME": "Алиса",
                "CONTACT__EMAIL": [{"VALUE": "alice@example.ru", "VALUE_TYPE": "WORK"}],
            },
        )

    def test_normalize_entity_dedup_settings_expands_shared_linked_settings_per_schema_entity(self):
        self.assertEqual(
            normalize_entity_dedup_settings(
                "linked_company_contact",
                {
                    "strategy": "update",
                    "fields": ["TITLE"],
                    "condition": "all",
                },
            ),
            {
                "company": {
                    "strategy": "update",
                    "fields": ["TITLE"],
                    "condition": "all",
                },
                "contact": {
                    "strategy": "update",
                    "fields": ["TITLE"],
                    "condition": "all",
                },
            },
        )

    def test_build_row_payload_formats_crm_multifields_using_field_ids(self):
        payload = build_row_payload(
            row=["Alice", "+123456789", "alice@example.com", "https://example.com", "@alice"],
            columns=["A", "B", "C", "D", "E"],
            mapping={
                "NAME": {
                    "column": "A",
                    "source_header": "First name",
                },
                "PHONE": {
                    "column": "B",
                    "source_header": "Phone",
                },
                "EMAIL": {
                    "column": "C",
                    "source_header": "Email",
                },
                "WEB": {
                    "column": "D",
                    "source_header": "Website",
                },
                "IM": {
                    "column": "E",
                    "source_header": "Messenger",
                },
            },
            fields=[
                {"id": "NAME", "type": "string", "multiple": False},
                {"id": "PHONE", "type": "crm_multifield", "multiple": True},
                {"id": "EMAIL", "type": "crm_multifield", "multiple": True},
                {"id": "WEB", "type": "crm_multifield", "multiple": True},
                {"id": "IM", "type": "crm_multifield", "multiple": True},
            ],
        )

        self.assertEqual(
            payload,
            {
                "NAME": "Alice",
                "PHONE": [{"VALUE": "+123456789", "VALUE_TYPE": "WORK"}],
                "EMAIL": [{"VALUE": "alice@example.com", "VALUE_TYPE": "WORK"}],
                "WEB": [{"VALUE": "https://example.com", "VALUE_TYPE": "WORK"}],
                "IM": [{"VALUE": "@alice", "VALUE_TYPE": "WORK"}],
            },
        )

    def test_build_row_payload_applies_value_mapping_for_status_field(self):
        payload = build_row_payload(
            row=["Alice", "Queued"],
            columns=["A", "B"],
            mapping={
                "TITLE": {
                    "column": "A",
                    "source_header": "Title",
                },
                "STAGE_ID": {
                    "column": "B",
                    "source_header": "Stage",
                    "value_mapping": {
                        "Queued": "IN_PROGRESS",
                    },
                },
            },
            fields=[
                {"id": "TITLE", "type": "string", "multiple": False},
                {
                    "id": "STAGE_ID",
                    "type": "crm_status",
                    "multiple": False,
                    "items": [
                        {"id": "NEW", "title": "New"},
                        {"id": "IN_PROGRESS", "title": "In progress"},
                    ],
                },
            ],
        )

        self.assertEqual(
            payload,
            {
                "TITLE": "Alice",
                "STAGE_ID": "IN_PROGRESS",
            },
        )

    def test_build_row_payload_normalizes_currency_alias_to_iso_code(self):
        payload = build_row_payload(
            row=["150000", "Рубли"],
            columns=["A", "B"],
            mapping={
                "OPPORTUNITY": {
                    "column": "A",
                    "source_header": "Сумма",
                },
                "CURRENCY_ID": {
                    "column": "B",
                    "source_header": "Валюта",
                },
            },
            fields=[
                {"id": "OPPORTUNITY", "type": "money", "multiple": False},
                {"id": "CURRENCY_ID", "type": "string", "multiple": False},
            ],
        )

        self.assertEqual(
            payload,
            {
                "OPPORTUNITY": 150000.0,
                "CURRENCY_ID": "RUB",
            },
        )

    def test_build_row_payload_formats_multiple_custom_list_field_as_array(self):
        payload = build_row_payload(
            row=["Alpha; Beta"],
            columns=["A"],
            mapping={
                "UF_CRM_TAGS": {
                    "column": "A",
                    "source_header": "Tags",
                },
            },
            fields=[
                {
                    "id": "UF_CRM_TAGS",
                    "type": "enumeration",
                    "multiple": True,
                    "items": [
                        {"id": "A", "title": "Alpha"},
                        {"id": "B", "title": "Beta"},
                    ],
                },
            ],
        )

        self.assertEqual(
            payload,
            {
                "UF_CRM_TAGS": ["A", "B"],
            },
        )

    def test_build_row_payload_normalizes_typed_custom_field_values(self):
        payload = build_row_payload(
            row=["да", "15", "12,50", "31.12.2026", "31.12.2026 18:45"],
            columns=["A", "B", "C", "D", "E"],
            mapping={
                "UF_CRM_IS_ACTIVE": {
                    "column": "A",
                    "source_header": "Active",
                },
                "UF_CRM_COUNT": {
                    "column": "B",
                    "source_header": "Count",
                },
                "UF_CRM_WEIGHT": {
                    "column": "C",
                    "source_header": "Weight",
                },
                "UF_CRM_START_DATE": {
                    "column": "D",
                    "source_header": "Start date",
                },
                "UF_CRM_VISIT_AT": {
                    "column": "E",
                    "source_header": "Visit at",
                },
            },
            fields=[
                {"id": "UF_CRM_IS_ACTIVE", "type": "boolean", "multiple": False},
                {"id": "UF_CRM_COUNT", "type": "integer", "multiple": False},
                {"id": "UF_CRM_WEIGHT", "type": "double", "multiple": False},
                {"id": "UF_CRM_START_DATE", "type": "date", "multiple": False},
                {"id": "UF_CRM_VISIT_AT", "type": "datetime", "multiple": False},
            ],
        )

        self.assertEqual(
            payload,
            {
                "UF_CRM_IS_ACTIVE": 1,
                "UF_CRM_COUNT": 15,
                "UF_CRM_WEIGHT": 12.5,
                "UF_CRM_START_DATE": "2026-12-31",
                "UF_CRM_VISIT_AT": "2026-12-31T18:45:00",
            },
        )

    def test_build_row_payload_formats_task_user_role_fields(self):
        payload = build_row_payload(
            row=["Task A", "59", "77; 78", "91\n92", "31.12.2026 18:45"],
            columns=["A", "B", "C", "D", "E"],
            mapping={
                "TITLE": {
                    "column": "A",
                    "source_header": "Task title",
                },
                "RESPONSIBLE_ID": {
                    "column": "B",
                    "source_header": "Responsible",
                },
                "ACCOMPLICES": {
                    "column": "C",
                    "source_header": "Accomplices",
                },
                "AUDITORS": {
                    "column": "D",
                    "source_header": "Auditors",
                },
                "DEADLINE": {
                    "column": "E",
                    "source_header": "Deadline",
                },
            },
            fields=[
                {"id": "TITLE", "type": "string", "multiple": False},
                {"id": "RESPONSIBLE_ID", "type": "integer", "multiple": False},
                {"id": "ACCOMPLICES", "type": "integer", "multiple": True},
                {"id": "AUDITORS", "type": "integer", "multiple": True},
                {"id": "DEADLINE", "type": "datetime", "multiple": False},
            ],
        )

        self.assertEqual(
            payload,
            {
                "TITLE": "Task A",
                "RESPONSIBLE_ID": 59,
                "ACCOMPLICES": [77, 78],
                "AUDITORS": [91, 92],
                "DEADLINE": "2026-12-31T18:45:00",
            },
        )

    def test_build_row_payload_resolves_task_user_role_fields_from_email_login_and_xml_id(self):
        user_results_by_filter = {
            (("EMAIL", "owner@example.com"),): [{"ID": 59}],
            (("LOGIN", "helper-login"),): [{"ID": 77}],
            (("LOGIN", "helper-two"),): [{"ID": 78}],
            (("LOGIN", "audit-ext"),): [],
            (("XML_ID", "audit-ext"),): [{"ID": 91}],
            (("LOGIN", "review-ext"),): [],
            (("XML_ID", "review-ext"),): [{"ID": 92}],
        }

        def get_users(*, filter=None):
            normalized_filter = tuple(sorted((filter or {}).items()))
            return FakeUsersRequest(user_results_by_filter.get(normalized_filter, []))

        account = SimpleNamespace(
            client=SimpleNamespace(
                user=SimpleNamespace(
                    get=get_users,
                )
            )
        )

        payload = build_row_payload(
            row=["Task A", "owner@example.com", "helper-login; helper-two", "audit-ext\nreview-ext", "31.12.2026 18:45"],
            columns=["A", "B", "C", "D", "E"],
            mapping={
                "TITLE": {
                    "column": "A",
                    "source_header": "Task title",
                },
                "RESPONSIBLE_ID": {
                    "column": "B",
                    "source_header": "Responsible",
                },
                "ACCOMPLICES": {
                    "column": "C",
                    "source_header": "Accomplices",
                },
                "AUDITORS": {
                    "column": "D",
                    "source_header": "Auditors",
                },
                "DEADLINE": {
                    "column": "E",
                    "source_header": "Deadline",
                },
            },
            fields=[
                {"id": "TITLE", "type": "string", "multiple": False},
                {"id": "RESPONSIBLE_ID", "type": "integer", "multiple": False},
                {"id": "ACCOMPLICES", "type": "integer", "multiple": True},
                {"id": "AUDITORS", "type": "integer", "multiple": True},
                {"id": "DEADLINE", "type": "datetime", "multiple": False},
            ],
            account=account,
        )

        self.assertEqual(
            payload,
            {
                "TITLE": "Task A",
                "RESPONSIBLE_ID": 59,
                "ACCOMPLICES": [77, 78],
                "AUDITORS": [91, 92],
                "DEADLINE": "2026-12-31T18:45:00",
            },
        )

    def test_build_row_payload_applies_default_task_responsible_when_mapping_is_missing(self):
        payload = build_row_payload(
            row=["Task A"],
            columns=["A"],
            mapping={
                "TITLE": {
                    "column": "A",
                    "source_header": "Task title",
                },
            },
            fields=[
                {"id": "TITLE", "type": "string", "multiple": False},
                {"id": "RESPONSIBLE_ID", "type": "integer", "multiple": False},
            ],
            default_field_values={
                "RESPONSIBLE_ID": "59",
            },
        )

        self.assertEqual(
            payload,
            {
                "TITLE": "Task A",
                "RESPONSIBLE_ID": 59,
            },
        )

    def test_build_row_payload_formats_subtask_parent_id(self):
        payload = build_row_payload(
            row=["Subtask A", "501"],
            columns=["A", "B"],
            mapping={
                "TITLE": {
                    "column": "A",
                    "source_header": "Task title",
                },
                "PARENT_ID": {
                    "column": "B",
                    "source_header": "Parent",
                },
            },
            fields=[
                {"id": "TITLE", "type": "string", "multiple": False},
                {"id": "PARENT_ID", "type": "integer", "multiple": False},
            ],
        )

        self.assertEqual(
            payload,
            {
                "TITLE": "Subtask A",
                "PARENT_ID": 501,
            },
        )

    def test_build_row_payload_for_task_comment_uses_task_and_message_only(self):
        account = SimpleNamespace(client=SimpleNamespace())

        payload = build_row_payload(
            row=["801", "Status update"],
            columns=["A", "B"],
            mapping={
                "TASK_ID": {
                    "column": "A",
                    "source_header": "Task",
                },
                "POST_MESSAGE": {
                    "column": "B",
                    "source_header": "Message",
                },
            },
            fields=[
                {"id": "TASK_ID", "type": "integer", "multiple": False},
                {"id": "POST_MESSAGE", "type": "text", "multiple": False},
            ],
            account=account,
        )

        self.assertEqual(
            payload,
            {
                "TASK_ID": 801,
                "POST_MESSAGE": "Status update",
            },
        )

    def test_build_row_payload_applies_default_task_comment_author_when_mapping_is_missing(self):
        payload = build_row_payload(
            row=["801", "Status update"],
            columns=["A", "B"],
            mapping={
                "TASK_ID": {
                    "column": "A",
                    "source_header": "Task",
                },
                "POST_MESSAGE": {
                    "column": "B",
                    "source_header": "Message",
                },
            },
            fields=[
                {"id": "TASK_ID", "type": "integer", "multiple": False},
                {"id": "AUTHOR_ID", "type": "integer", "multiple": False},
                {"id": "POST_MESSAGE", "type": "text", "multiple": False},
            ],
            default_field_values={
                "AUTHOR_ID": "59",
            },
        )

        self.assertEqual(
            payload,
            {
                "TASK_ID": 801,
                "AUTHOR_ID": 59,
                "POST_MESSAGE": "Status update",
            },
        )

    @patch("importer.services.import_execution.BitrixAPIRequest", create=True)
    def test_create_task_comment_uses_chat_message_api(self, bitrix_api_request):
        bitrix_api_request.return_value = SimpleNamespace(result={"result": True})
        account = SimpleNamespace(client=SimpleNamespace())

        result = create_entity_record(
            account,
            "task_comment",
            {
                "TASK_ID": 801,
                "POST_MESSAGE": "Status update",
            },
        )

        self.assertIsNone(result)
        bitrix_api_request.assert_called_once_with(
            bitrix_token=account,
            api_method="tasks.task.chat.message.send",
            params={
                "fields": {
                    "taskId": 801,
                    "text": "Status update",
                }
            },
        )

    @patch("importer.services.import_execution.BitrixAPIRequest", create=True)
    def test_create_task_comment_with_author_uses_comment_api(self, bitrix_api_request):
        bitrix_api_request.return_value = SimpleNamespace(result=915)
        account = SimpleNamespace(client=SimpleNamespace())

        result = create_entity_record(
            account,
            "task_comment",
            {
                "TASK_ID": 801,
                "AUTHOR_ID": 59,
                "POST_MESSAGE": "Status update",
            },
        )

        self.assertEqual(result, 915)
        bitrix_api_request.assert_called_once_with(
            bitrix_token=account,
            api_method="task.commentitem.add",
            params={
                "TASKID": 801,
                "FIELDS": {
                    "POST_MESSAGE": "Status update",
                    "AUTHOR_ID": 59,
                }
            },
        )

    @patch("importer.services.import_execution.BitrixAPIRequest", create=True)
    def test_create_crm_activity_call_requires_communication_value(self, bitrix_api_request):
        account = SimpleNamespace(client=SimpleNamespace())

        with self.assertRaisesMessage(ValueError, "COMMUNICATIONS_VALUE обязателен для звонка CRM"):
            create_entity_record(
                account,
                "crm_activity",
                {
                    "OWNER_TYPE_ID": "2",
                    "OWNER_ID": "63",
                    "TYPE_ID": "2",
                    "SUBJECT": "Звонок по презентации",
                },
            )

        bitrix_api_request.assert_not_called()

    @patch("importer.services.import_execution.BitrixAPIRequest", create=True)
    def test_create_crm_activity_call_passes_phone_in_communications(self, bitrix_api_request):
        bitrix_api_request.return_value = SimpleNamespace(result=913)
        account = SimpleNamespace(client=SimpleNamespace())

        result = create_entity_record(
            account,
            "crm_activity",
            {
                "OWNER_TYPE_ID": "2",
                "OWNER_ID": "63",
                "TYPE_ID": "2",
                "SUBJECT": "Звонок по презентации",
                "COMMUNICATIONS_VALUE": "+79991234567",
            },
        )

        self.assertEqual(result, 913)
        bitrix_api_request.assert_called_once_with(
            bitrix_token=account,
            api_method="crm.activity.add",
            params={
                "fields": {
                    "OWNER_TYPE_ID": 2,
                    "OWNER_ID": 63,
                    "TYPE_ID": 2,
                    "SUBJECT": "Звонок по презентации",
                    "COMMUNICATIONS": [
                        {
                            "ENTITY_ID": 63,
                            "ENTITY_TYPE_ID": 2,
                            "TYPE": "PHONE",
                            "VALUE": "+79991234567",
                        }
                    ],
                }
            },
        )

    @patch("importer.services.import_execution.BitrixAPIRequest", create=True)
    def test_create_crm_note_uses_timeline_comment_api(self, bitrix_api_request):
        bitrix_api_request.return_value = SimpleNamespace(result=927)
        account = SimpleNamespace(client=SimpleNamespace())

        result = create_entity_record(
            account,
            "crm_note",
            {
                "ENTITY_TYPE": "deal",
                "ENTITY_ID": "55",
                "COMMENT": "Договор согласован, ожидаем подписания",
                "CREATED_TIME": "2026-05-17T11:30:00",
            },
        )

        self.assertEqual(result, 927)
        bitrix_api_request.assert_called_once_with(
            bitrix_token=account,
            api_method="crm.timeline.comment.add",
            params={
                "fields": {
                    "ENTITY_TYPE": "DEAL",
                    "ENTITY_ID": 55,
                    "COMMENT": "Договор согласован, ожидаем подписания",
                    "CREATED_TIME": "2026-05-17T11:30:00",
                }
            },
        )

    @patch("importer.services.import_execution.BitrixAPIRequest", create=True)
    def test_create_smart_process_item_uses_universal_crm_item_api(self, bitrix_api_request):
        bitrix_api_request.return_value = SimpleNamespace(result={"item": {"id": 501}})
        account = SimpleNamespace(client=SimpleNamespace())

        result = create_entity_record(
            account,
            "smart_process",
            {
                "title": "Новый элемент",
                "stageId": "DT128_0:NEW",
            },
            context={"entity_config": {"entityTypeId": 128}},
        )

        self.assertEqual(result, 501)
        bitrix_api_request.assert_called_once_with(
            bitrix_token=account,
            api_method="crm.item.add",
            params={
                "entityTypeId": 128,
                "fields": {
                    "title": "Новый элемент",
                    "stageId": "DT128_0:NEW",
                },
            },
        )

    def test_smart_process_dedup_is_forced_to_create_only(self):
        self.assertEqual(
            normalize_entity_dedup_settings(
                "smart_process",
                {
                    "strategy": "update",
                    "fields": ["title"],
                    "condition": "all",
                },
            ),
            {
                "strategy": "create",
                "fields": [],
                "condition": "any",
            },
        )

    @patch("importer.services.import_execution.attach_file_to_task", create=True)
    @patch("importer.services.import_execution.download_attachment_source", create=True)
    def test_create_task_attachment_uploads_downloaded_file(self, download_attachment_source, attach_file_to_task):
        download_attachment_source.return_value = {
            "content": b"hello world",
            "file_name": "brief.txt",
            "content_type": "text/plain",
        }
        attach_file_to_task.return_value = {"attachment_id": 7001}

        account = SimpleNamespace(client=SimpleNamespace())

        result = create_entity_record(
            account,
            "task_attachment",
            {
                "TASK_ID": 801,
                "FILE_URL": "https://files.example.com/brief.txt",
                "FILE_NAME": "Renamed brief.txt",
            },
        )

        self.assertEqual(result, 7001)
        download_attachment_source.assert_called_once_with("https://files.example.com/brief.txt")
        attach_file_to_task.assert_called_once_with(
            account,
            task_id=801,
            file_name="Renamed brief.txt",
            content=b"hello world",
            content_type="text/plain",
        )

    def test_build_row_payload_formats_richer_task_fields(self):
        user_results_by_filter = {
            (("EMAIL", "creator@example.com"),): [{"ID": 17}],
        }

        def get_users(*, filter=None):
            normalized_filter = tuple(sorted((filter or {}).items()))
            return FakeUsersRequest(user_results_by_filter.get(normalized_filter, []))

        account = SimpleNamespace(
            client=SimpleNamespace(
                user=SimpleNamespace(
                    get=get_users,
                )
            )
        )

        payload = build_row_payload(
            row=[
                "Task B",
                "Long task description",
                "creator@example.com",
                "15",
                "2",
                "alpha; beta",
                "31.12.2026 09:00",
                "31.12.2026 18:00",
                "01.01.2027 12:00",
            ],
            columns=["A", "B", "C", "D", "E", "F", "G", "H", "I"],
            mapping={
                "TITLE": {
                    "column": "A",
                    "source_header": "Task title",
                },
                "DESCRIPTION": {
                    "column": "B",
                    "source_header": "Description",
                },
                "CREATED_BY": {
                    "column": "C",
                    "source_header": "Creator",
                },
                "GROUP_ID": {
                    "column": "D",
                    "source_header": "Project",
                },
                "PRIORITY": {
                    "column": "E",
                    "source_header": "Priority",
                },
                "TAGS": {
                    "column": "F",
                    "source_header": "Tags",
                },
                "START_DATE_PLAN": {
                    "column": "G",
                    "source_header": "Start",
                },
                "END_DATE_PLAN": {
                    "column": "H",
                    "source_header": "End",
                },
                "DEADLINE": {
                    "column": "I",
                    "source_header": "Deadline",
                },
            },
            fields=[
                {"id": "TITLE", "type": "string", "multiple": False},
                {"id": "DESCRIPTION", "type": "text", "multiple": False},
                {"id": "CREATED_BY", "type": "integer", "multiple": False},
                {"id": "GROUP_ID", "type": "integer", "multiple": False},
                {"id": "PRIORITY", "type": "integer", "multiple": False},
                {"id": "TAGS", "type": "string", "multiple": True},
                {"id": "START_DATE_PLAN", "type": "datetime", "multiple": False},
                {"id": "END_DATE_PLAN", "type": "datetime", "multiple": False},
                {"id": "DEADLINE", "type": "datetime", "multiple": False},
            ],
            account=account,
        )

        self.assertEqual(
            payload,
            {
                "TITLE": "Task B",
                "DESCRIPTION": "Long task description",
                "CREATED_BY": 17,
                "GROUP_ID": 15,
                "PRIORITY": 2,
                "TAGS": ["alpha", "beta"],
                "START_DATE_PLAN": "2026-12-31T09:00:00",
                "END_DATE_PLAN": "2026-12-31T18:00:00",
                "DEADLINE": "2027-01-01T12:00:00",
            },
        )
