import os
import shutil
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings

from importer.models import ImportSession
from importer.services.task_bulk_attach import execute_task_bulk_attach, fetch_task_entities_page, fetch_task_ids


class _FakeBitrixRequest:
    def __init__(self, *, result, total=None, next_start=None):
        self.response = SimpleNamespace(
            result=result,
            total=total,
            next=next_start,
        )


class TaskBulkAttachServiceTest(TestCase):
    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()

    @patch("importer.services.task_bulk_attach.BitrixAPIRequest")
    def test_fetch_task_entities_page_uses_task_list_api(self, bitrix_api_request):
        account = SimpleNamespace()
        bitrix_api_request.return_value = _FakeBitrixRequest(
            result={
                "tasks": [
                    {"id": "801", "title": "Prepare brief"},
                    {"id": "802", "title": "Review assets"},
                ]
            },
            total=2,
            next_start=None,
        )

        page = fetch_task_entities_page(account, {"STATUS": "2"}, start=0)

        self.assertEqual(
            page,
            {
                "items": [
                    {"id": "801", "title": "Prepare brief"},
                    {"id": "802", "title": "Review assets"},
                ],
                "total": 2,
                "next": None,
            },
        )
        self.assertEqual(
            bitrix_api_request.call_args.kwargs,
            {
                "bitrix_token": account,
                "api_method": "tasks.task.list",
                "params": {
                    "filter": {"STATUS": "2"},
                    "select": ["ID", "TITLE"],
                    "start": 0,
                },
            },
        )

    @patch("importer.services.task_bulk_attach.fetch_task_entities_page")
    def test_fetch_task_ids_collects_all_pages(self, fetch_task_entities_page):
        account = SimpleNamespace()
        fetch_task_entities_page.side_effect = [
            {
                "items": [{"id": "801", "title": "Prepare brief"}],
                "total": 2,
                "next": 50,
            },
            {
                "items": [{"id": "802", "title": "Review assets"}],
                "total": 2,
                "next": None,
            },
        ]

        task_ids = fetch_task_ids(account, {"STATUS": "2"})

        self.assertEqual(task_ids, [801, 802])

    @patch("importer.services.task_bulk_attach.attach_file_to_task")
    @patch("importer.services.task_bulk_attach.fetch_task_ids")
    def test_execute_task_bulk_attach_reads_uploaded_file_once_and_attaches_to_each_task(self, fetch_task_ids, attach_file_to_task):
        fetch_task_ids.return_value = [801, 802]
        attach_file_to_task.return_value = {"attachment_id": 7001}
        account = SimpleNamespace()

        upload_dir = os.path.join(self.media_root, "bulk-attach-uploads", "file-123")
        os.makedirs(upload_dir, exist_ok=True)
        with open(os.path.join(upload_dir, "brief.txt"), "wb") as fh:
            fh.write(b"hello world")

        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.TASK_ATTACHMENT,
            source_format="bulk_attach",
            status=ImportSession.Status.DRAFT,
            original_filename="Task bulk attach",
            summary={
                "bulk_attach": {
                    "mode": "task",
                    "entity_type": "task",
                    "filter": {"STATUS": "2"},
                    "file_id": "file-123",
                    "file_name": "brief.txt",
                    "file_url": "",
                }
            },
        )

        result = execute_task_bulk_attach(session=session, account=account)

        self.assertEqual(
            result,
            {
                "total": 2,
                "successful": 2,
                "failed": 0,
                "results": [
                    {"entity_id": 801, "status": "success"},
                    {"entity_id": 802, "status": "success"},
                ],
            },
        )
        self.assertEqual(session.total_rows, 2)
        self.assertEqual(session.processed_rows, 2)
        self.assertEqual(session.successful_rows, 2)
        self.assertEqual(session.failed_rows, 0)
        self.assertEqual(attach_file_to_task.call_count, 2)
        attach_file_to_task.assert_any_call(
            account,
            task_id=801,
            file_name="brief.txt",
            content=b"hello world",
        )
