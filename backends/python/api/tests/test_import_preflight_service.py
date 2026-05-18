from django.test import SimpleTestCase

from importer.services.preflight import build_mapping_preflight


class ImportPreflightServiceTest(SimpleTestCase):
    def test_task_preflight_allows_runtime_responsible_without_explicit_mapping(self):
        preflight = build_mapping_preflight(
            entity_type="task",
            rows=[
                ["Task title", "Parent"],
                ["Subtask A", "501"],
            ],
            row_numbers=[1, 2],
            columns=["A", "B"],
            data_start_row=2,
            mapping={
                "TITLE": {
                    "source_header": "Task title",
                    "column": "A",
                },
                "PARENT_ID": {
                    "source_header": "Parent",
                    "column": "B",
                },
            },
            fields=[
                {"id": "TITLE", "title": "Название задачи", "type": "string", "required": True},
                {"id": "RESPONSIBLE_ID", "title": "Ответственный (ID)", "type": "integer", "required": True},
                {"id": "PARENT_ID", "title": "ID родительской задачи", "type": "integer", "required": False},
            ],
            dedup_settings={},
            default_field_values={},
        )

        self.assertEqual(preflight["blocking_issue_count"], 0)
        self.assertEqual(preflight["issues"], [])

    def test_task_preflight_allows_runtime_creator_without_explicit_mapping(self):
        preflight = build_mapping_preflight(
            entity_type="task",
            rows=[
                ["Task title"],
                ["Subtask A"],
            ],
            row_numbers=[1, 2],
            columns=["A"],
            data_start_row=2,
            mapping={
                "TITLE": {
                    "source_header": "Task title",
                    "column": "A",
                },
            },
            fields=[
                {"id": "TITLE", "title": "Название задачи", "type": "string", "required": True},
                {"id": "RESPONSIBLE_ID", "title": "Ответственный (ID)", "type": "integer", "required": True},
                {"id": "CREATED_BY", "title": "Постановщик (ID)", "type": "integer", "required": True},
            ],
            dedup_settings={},
            default_field_values={"RESPONSIBLE_ID": "59"},
        )

        self.assertEqual(preflight["blocking_issue_count"], 0)
        self.assertEqual(preflight["issues"], [])

    def test_task_comment_preflight_allows_runtime_author_without_explicit_mapping(self):
        preflight = build_mapping_preflight(
            entity_type="task_comment",
            rows=[
                ["Task", "Message"],
                ["801", "Status update"],
            ],
            row_numbers=[1, 2],
            columns=["A", "B"],
            data_start_row=2,
            mapping={
                "TASK_ID": {
                    "source_header": "Task",
                    "column": "A",
                },
                "POST_MESSAGE": {
                    "source_header": "Message",
                    "column": "B",
                },
            },
            fields=[
                {"id": "TASK_ID", "title": "ID задачи", "type": "string", "required": True},
                {"id": "AUTHOR_ID", "title": "Пользователь", "type": "integer", "required": True},
                {"id": "POST_MESSAGE", "title": "Комментарий", "type": "text", "required": True},
            ],
            dedup_settings={},
            default_field_values={},
        )

        self.assertEqual(preflight["blocking_issue_count"], 0)
        self.assertEqual(preflight["issues"], [])
