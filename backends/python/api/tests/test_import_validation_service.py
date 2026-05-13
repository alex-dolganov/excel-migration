from types import SimpleNamespace

from django.test import SimpleTestCase

from importer.services.validation import build_validation_result, validate_field_value


class FakeUsersRequest:
    def __init__(self, result):
        self.result = result


class FakeTasksRequest:
    def __init__(self, result):
        self.result = result


class ImportValidationServiceTest(SimpleTestCase):
    def test_validate_field_value_supports_crm_multifield_phone_and_email(self):
        phone_issue = validate_field_value(
            field={"id": "PHONE", "title": "Phone", "type": "crm_multifield", "required": False},
            value="12",
            row_number=2,
            column="B",
            source_header="Phone",
            target_field="PHONE",
        )
        email_issue = validate_field_value(
            field={"id": "EMAIL", "title": "Email", "type": "crm_multifield", "required": False},
            value="broken-email",
            row_number=2,
            column="C",
            source_header="Email",
            target_field="EMAIL",
        )

        self.assertEqual(phone_issue["code"], "phone")
        self.assertEqual(phone_issue["message"], 'Field "Phone" must contain a valid phone')
        self.assertEqual(email_issue["code"], "email")
        self.assertEqual(email_issue["message"], 'Field "Email" must contain a valid email')

    def test_build_validation_result_requires_value_mapping_for_unknown_stage_value(self):
        validation_result = build_validation_result(
            rows=[
                ["Title", "Stage"],
                ["Lead A", "Queued"],
            ],
            row_numbers=[1, 2],
            columns=["A", "B"],
            data_start_row=2,
            mapping={
                "TITLE": {
                    "source_header": "Title",
                    "column": "A",
                    "target_field": "TITLE",
                },
                "STAGE_ID": {
                    "source_header": "Stage",
                    "column": "B",
                    "target_field": "STAGE_ID",
                },
            },
            fields=[
                {"id": "TITLE", "title": "Title", "type": "string", "required": False},
                {
                    "id": "STAGE_ID",
                    "title": "Stage",
                    "type": "crm_status",
                    "required": False,
                    "items": [
                        {"id": "NEW", "title": "New"},
                        {"id": "IN_PROGRESS", "title": "In progress"},
                    ],
                },
            ],
        )

        self.assertEqual(validation_result["issue_count"], 1)
        self.assertEqual(validation_result["issues"][0]["code"], "enum")
        self.assertEqual(validation_result["issues"][0]["message"], 'Field "Stage" must contain a mapped list value')

    def test_build_validation_result_accepts_stage_value_mapping(self):
        validation_result = build_validation_result(
            rows=[
                ["Title", "Stage"],
                ["Lead A", "Queued"],
            ],
            row_numbers=[1, 2],
            columns=["A", "B"],
            data_start_row=2,
            mapping={
                "TITLE": {
                    "source_header": "Title",
                    "column": "A",
                    "target_field": "TITLE",
                },
                "STAGE_ID": {
                    "source_header": "Stage",
                    "column": "B",
                    "target_field": "STAGE_ID",
                    "value_mapping": {
                        "Queued": "IN_PROGRESS",
                    },
                },
            },
            fields=[
                {"id": "TITLE", "title": "Title", "type": "string", "required": False},
                {
                    "id": "STAGE_ID",
                    "title": "Stage",
                    "type": "crm_status",
                    "required": False,
                    "items": [
                        {"id": "NEW", "title": "New"},
                        {"id": "IN_PROGRESS", "title": "In progress"},
                    ],
                },
            ],
        )

        self.assertEqual(validation_result["issue_count"], 0)
        self.assertEqual(validation_result["valid_rows"], 1)

    def test_build_validation_result_accepts_multiple_custom_list_values(self):
        validation_result = build_validation_result(
            rows=[
                ["Title", "Tags"],
                ["Lead A", "Alpha; Beta"],
            ],
            row_numbers=[1, 2],
            columns=["A", "B"],
            data_start_row=2,
            mapping={
                "TITLE": {
                    "source_header": "Title",
                    "column": "A",
                    "target_field": "TITLE",
                },
                "UF_CRM_TAGS": {
                    "source_header": "Tags",
                    "column": "B",
                    "target_field": "UF_CRM_TAGS",
                },
            },
            fields=[
                {"id": "TITLE", "title": "Title", "type": "string", "required": False, "multiple": False},
                {
                    "id": "UF_CRM_TAGS",
                    "title": "Tags",
                    "type": "enumeration",
                    "required": False,
                    "multiple": True,
                    "items": [
                        {"id": "A", "title": "Alpha"},
                        {"id": "B", "title": "Beta"},
                    ],
                },
            ],
        )

        self.assertEqual(validation_result["issue_count"], 0)
        self.assertEqual(validation_result["valid_rows"], 1)

    def test_validate_field_value_accepts_datetime_with_time_component(self):
        issue = validate_field_value(
            field={"id": "UF_CRM_VISIT_AT", "title": "Visit at", "type": "datetime", "required": False},
            value="31.12.2026 18:45",
            row_number=2,
            column="D",
            source_header="Visit at",
            target_field="UF_CRM_VISIT_AT",
        )

        self.assertIsNone(issue)

    def test_build_validation_result_requires_communication_value_for_crm_activity_call(self):
        validation_result = build_validation_result(
            rows=[
                ["Тип активности", "Телефон / Email"],
                ["Звонок", ""],
            ],
            row_numbers=[1, 2],
            columns=["A", "B"],
            data_start_row=2,
            mapping={
                "TYPE_ID": {
                    "source_header": "Тип активности",
                    "column": "A",
                    "target_field": "TYPE_ID",
                },
                "COMMUNICATIONS_VALUE": {
                    "source_header": "Телефон / Email",
                    "column": "B",
                    "target_field": "COMMUNICATIONS_VALUE",
                },
            },
            fields=[
                {
                    "id": "TYPE_ID",
                    "title": "Тип активности",
                    "type": "string",
                    "required": True,
                    "multiple": False,
                    "items": [
                        {"id": "1", "title": "Встреча"},
                        {"id": "2", "title": "Звонок"},
                        {"id": "4", "title": "Email"},
                    ],
                },
                {
                    "id": "COMMUNICATIONS_VALUE",
                    "title": "Телефон / Email (для звонков и писем)",
                    "type": "string",
                    "required": False,
                    "multiple": False,
                },
            ],
        )

        self.assertEqual(validation_result["issue_count"], 1)
        self.assertEqual(validation_result["issues"][0]["target_field"], "COMMUNICATIONS_VALUE")
        self.assertEqual(validation_result["issues"][0]["code"], "required")
        self.assertEqual(
            validation_result["issues"][0]["message"],
            'Field "Телефон / Email (для звонков и писем)" is required for call activities',
        )

    def test_build_validation_result_accepts_phone_for_crm_activity_call(self):
        validation_result = build_validation_result(
            rows=[
                ["Тип активности", "Телефон / Email"],
                ["Звонок", "+79991234567"],
            ],
            row_numbers=[1, 2],
            columns=["A", "B"],
            data_start_row=2,
            mapping={
                "TYPE_ID": {
                    "source_header": "Тип активности",
                    "column": "A",
                    "target_field": "TYPE_ID",
                },
                "COMMUNICATIONS_VALUE": {
                    "source_header": "Телефон / Email",
                    "column": "B",
                    "target_field": "COMMUNICATIONS_VALUE",
                },
            },
            fields=[
                {
                    "id": "TYPE_ID",
                    "title": "Тип активности",
                    "type": "string",
                    "required": True,
                    "multiple": False,
                    "items": [
                        {"id": "1", "title": "Встреча"},
                        {"id": "2", "title": "Звонок"},
                        {"id": "4", "title": "Email"},
                    ],
                },
                {
                    "id": "COMMUNICATIONS_VALUE",
                    "title": "Телефон / Email (для звонков и писем)",
                    "type": "string",
                    "required": False,
                    "multiple": False,
                },
            ],
        )

        self.assertEqual(validation_result["issue_count"], 0)
        self.assertEqual(validation_result["valid_rows"], 1)

    def test_build_validation_result_accepts_task_user_references_by_email_login_and_xml_id(self):
        user_results_by_filter = {
            (("EMAIL", "owner@example.com"),): [{"ID": 59}],
            (("LOGIN", "helper-login"),): [{"ID": 77}],
            (("LOGIN", "audit-ext"),): [],
            (("XML_ID", "audit-ext"),): [{"ID": 91}],
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

        validation_result = build_validation_result(
            rows=[
                ["Task title", "Responsible", "Accomplices", "Auditors"],
                ["Task A", "owner@example.com", "helper-login", "audit-ext"],
            ],
            row_numbers=[1, 2],
            columns=["A", "B", "C", "D"],
            data_start_row=2,
            mapping={
                "TITLE": {
                    "source_header": "Task title",
                    "column": "A",
                    "target_field": "TITLE",
                },
                "RESPONSIBLE_ID": {
                    "source_header": "Responsible",
                    "column": "B",
                    "target_field": "RESPONSIBLE_ID",
                },
                "ACCOMPLICES": {
                    "source_header": "Accomplices",
                    "column": "C",
                    "target_field": "ACCOMPLICES",
                },
                "AUDITORS": {
                    "source_header": "Auditors",
                    "column": "D",
                    "target_field": "AUDITORS",
                },
            },
            fields=[
                {"id": "TITLE", "title": "Task title", "type": "string", "required": True, "multiple": False},
                {"id": "RESPONSIBLE_ID", "title": "Responsible user ID", "type": "integer", "required": False, "multiple": False},
                {"id": "ACCOMPLICES", "title": "Accomplice user IDs", "type": "integer", "required": False, "multiple": True},
                {"id": "AUDITORS", "title": "Auditor user IDs", "type": "integer", "required": False, "multiple": True},
            ],
            account=account,
        )

        self.assertEqual(validation_result["issue_count"], 0)
        self.assertEqual(validation_result["valid_rows"], 1)

    def test_build_validation_result_requires_task_responsible_mapping_value(self):
        validation_result = build_validation_result(
            rows=[
                ["Task title", "Responsible"],
                ["Task A", ""],
            ],
            row_numbers=[1, 2],
            columns=["A", "B"],
            data_start_row=2,
            mapping={
                "TITLE": {
                    "source_header": "Task title",
                    "column": "A",
                    "target_field": "TITLE",
                },
                "RESPONSIBLE_ID": {
                    "source_header": "Responsible",
                    "column": "B",
                    "target_field": "RESPONSIBLE_ID",
                },
            },
            fields=[
                {"id": "TITLE", "title": "Task title", "type": "string", "required": True, "multiple": False},
                {"id": "RESPONSIBLE_ID", "title": "Responsible user ID", "type": "integer", "required": True, "multiple": False},
            ],
        )

        self.assertEqual(validation_result["issue_count"], 1)
        self.assertEqual(validation_result["issues"][0]["code"], "required")
        self.assertEqual(validation_result["issues"][0]["target_field"], "RESPONSIBLE_ID")
        self.assertEqual(validation_result["issues"][0]["message"], 'Field "Responsible user ID" is required')

    def test_build_validation_result_accepts_task_default_responsible_when_column_is_not_mapped(self):
        validation_result = build_validation_result(
            rows=[
                ["Task title"],
                ["Task A"],
            ],
            row_numbers=[1, 2],
            columns=["A"],
            data_start_row=2,
            mapping={
                "TITLE": {
                    "source_header": "Task title",
                    "column": "A",
                    "target_field": "TITLE",
                },
            },
            fields=[
                {"id": "TITLE", "title": "Task title", "type": "string", "required": True, "multiple": False},
                {"id": "RESPONSIBLE_ID", "title": "Responsible user ID", "type": "integer", "required": True, "multiple": False},
            ],
            default_field_values={
                "RESPONSIBLE_ID": "59",
            },
        )

        self.assertEqual(validation_result["issue_count"], 0)
        self.assertEqual(validation_result["valid_rows"], 1)

    def test_build_validation_result_accepts_task_parent_reference_by_xml_id(self):
        task_results_by_filter = {
            (("XML_ID", "task-ext-1"),): [{"ID": 501}],
        }

        def list_tasks(*, filter=None, select=None):
            normalized_filter = tuple(sorted((filter or {}).items()))
            return FakeTasksRequest(task_results_by_filter.get(normalized_filter, []))

        account = SimpleNamespace(
            client=SimpleNamespace(
                tasks=SimpleNamespace(
                    task=SimpleNamespace(
                        list=list_tasks,
                    )
                )
            )
        )

        validation_result = build_validation_result(
            rows=[
                ["Task title", "Parent"],
                ["Subtask A", "task-ext-1"],
            ],
            row_numbers=[1, 2],
            columns=["A", "B"],
            data_start_row=2,
            mapping={
                "TITLE": {
                    "source_header": "Task title",
                    "column": "A",
                    "target_field": "TITLE",
                },
                "PARENT_ID": {
                    "source_header": "Parent",
                    "column": "B",
                    "target_field": "PARENT_ID",
                },
            },
            fields=[
                {"id": "TITLE", "title": "Task title", "type": "string", "required": True, "multiple": False},
                {"id": "PARENT_ID", "title": "Parent task ID", "type": "integer", "required": False, "multiple": False},
            ],
            account=account,
        )

        self.assertEqual(validation_result["issue_count"], 0)
        self.assertEqual(validation_result["valid_rows"], 1)

    def test_build_validation_result_accepts_task_child_reference_by_xml_id(self):
        task_results_by_filter = {
            (("XML_ID", "task-ext-1"),): [{"ID": 801}],
        }

        def list_tasks(*, filter=None, select=None):
            normalized_filter = tuple(sorted((filter or {}).items()))
            return FakeTasksRequest(task_results_by_filter.get(normalized_filter, []))

        account = SimpleNamespace(
            client=SimpleNamespace(
                tasks=SimpleNamespace(
                    task=SimpleNamespace(
                        list=list_tasks,
                    )
                )
            )
        )

        validation_result = build_validation_result(
            rows=[
                ["Task", "Message"],
                ["task-ext-1", "Status update"],
            ],
            row_numbers=[1, 2],
            columns=["A", "B"],
            data_start_row=2,
            mapping={
                "TASK_ID": {
                    "source_header": "Task",
                    "column": "A",
                    "target_field": "TASK_ID",
                },
                "POST_MESSAGE": {
                    "source_header": "Message",
                    "column": "B",
                    "target_field": "POST_MESSAGE",
                },
            },
            fields=[
                {"id": "TASK_ID", "title": "Task ID", "type": "integer", "required": True, "multiple": False},
                {"id": "POST_MESSAGE", "title": "Comment text", "type": "text", "required": True, "multiple": False},
            ],
            account=account,
        )

        self.assertEqual(validation_result["issue_count"], 0)
        self.assertEqual(validation_result["valid_rows"], 1)

    def test_validate_field_value_rejects_unknown_task_user_reference(self):
        account = SimpleNamespace(
            client=SimpleNamespace(
                user=SimpleNamespace(
                    get=lambda *, filter=None: FakeUsersRequest([]),
                )
            )
        )

        issue = validate_field_value(
            field={"id": "RESPONSIBLE_ID", "title": "Responsible user ID", "type": "integer", "required": False, "multiple": False},
            value="missing@example.com",
            row_number=2,
            column="B",
            source_header="Responsible",
            target_field="RESPONSIBLE_ID",
            account=account,
        )

        self.assertEqual(issue["code"], "user")
        self.assertEqual(issue["message"], 'Field "Responsible user ID" must contain a valid Bitrix user reference')

    def test_build_validation_result_accepts_richer_task_fields(self):
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

        validation_result = build_validation_result(
            rows=[
                ["Task title", "Description", "Creator", "Project", "Priority", "Tags", "Start", "End", "Deadline"],
                ["Task B", "Long task description", "creator@example.com", "15", "2", "alpha; beta", "31.12.2026 09:00", "31.12.2026 18:00", "01.01.2027 12:00"],
            ],
            row_numbers=[1, 2],
            columns=["A", "B", "C", "D", "E", "F", "G", "H", "I"],
            data_start_row=2,
            mapping={
                "TITLE": {"source_header": "Task title", "column": "A", "target_field": "TITLE"},
                "DESCRIPTION": {"source_header": "Description", "column": "B", "target_field": "DESCRIPTION"},
                "CREATED_BY": {"source_header": "Creator", "column": "C", "target_field": "CREATED_BY"},
                "GROUP_ID": {"source_header": "Project", "column": "D", "target_field": "GROUP_ID"},
                "PRIORITY": {"source_header": "Priority", "column": "E", "target_field": "PRIORITY"},
                "TAGS": {"source_header": "Tags", "column": "F", "target_field": "TAGS"},
                "START_DATE_PLAN": {"source_header": "Start", "column": "G", "target_field": "START_DATE_PLAN"},
                "END_DATE_PLAN": {"source_header": "End", "column": "H", "target_field": "END_DATE_PLAN"},
                "DEADLINE": {"source_header": "Deadline", "column": "I", "target_field": "DEADLINE"},
            },
            fields=[
                {"id": "TITLE", "title": "Task title", "type": "string", "required": True, "multiple": False},
                {"id": "DESCRIPTION", "title": "Description", "type": "text", "required": False, "multiple": False},
                {"id": "CREATED_BY", "title": "Creator user ID", "type": "integer", "required": False, "multiple": False},
                {"id": "GROUP_ID", "title": "Project group ID", "type": "integer", "required": False, "multiple": False},
                {"id": "PRIORITY", "title": "Priority", "type": "integer", "required": False, "multiple": False},
                {"id": "TAGS", "title": "Tags", "type": "string", "required": False, "multiple": True},
                {"id": "START_DATE_PLAN", "title": "Planned start date", "type": "datetime", "required": False, "multiple": False},
                {"id": "END_DATE_PLAN", "title": "Planned end date", "type": "datetime", "required": False, "multiple": False},
                {"id": "DEADLINE", "title": "Deadline", "type": "datetime", "required": False, "multiple": False},
            ],
            account=account,
        )

        self.assertEqual(validation_result["issue_count"], 0)
        self.assertEqual(validation_result["valid_rows"], 1)
