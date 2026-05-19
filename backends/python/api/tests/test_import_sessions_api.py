from types import SimpleNamespace
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from importer.models import ImportSession


class ImportSessionsApiTest(TestCase):
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_list_sessions_returns_portal_sessions_ordered_by_newest(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.DRAFT,
            original_filename="a.xlsx",
        )

        response = self.client.get(
            reverse("importer:sessions"),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 1)
        self.assertEqual(response.json()["items"][0]["summary"], {})
        self.assertNotIn("preview_data", response.json()["items"][0])
        self.assertNotIn("stored_file_name", response.json()["items"][0])

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_list_sessions_includes_import_run_summary_for_history_breakdown(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.CONTACT,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.COMPLETED,
            original_filename="contacts.xlsx",
            preview_data={
                "headers": ["Name", "Phone"],
                "rows": [["Alice", "+79990000000"]],
            },
            summary={
                "import_run": {
                    "created_rows": 3,
                    "updated_rows": 2,
                    "skipped_rows": 1,
                    "failed_rows": 1,
                    "results": [{"row_number": 2, "status": "created", "record_id": 101}],
                },
                "dry_run": {
                    "results": [{"row_number": 2, "status": "created"}],
                },
                "job": {"state": "running", "worker_id": "worker-1"},
            },
        )

        response = self.client.get(
            reverse("importer:sessions"),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["summary"], {
            "import_run": {
                "created_rows": 3,
                "updated_rows": 2,
                "skipped_rows": 1,
                "failed_rows": 1,
            },
            "job": {
                "state": "running",
            },
        })
        self.assertNotIn("preview_data", response.json()["items"][0])

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_get_session_returns_single_portal_session_snapshot(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.CONTACT,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.RUNNING,
            original_filename="contacts.xlsx",
            summary={"job": {"state": "queued"}},
        )

        response = self.client.get(
            reverse("importer:session-detail", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["id"], str(session.id))
        self.assertEqual(response.json()["item"]["status"], ImportSession.Status.RUNNING)
        self.assertEqual(response.json()["item"]["summary"], {"job": {"state": "queued"}})

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_create_session_returns_created_draft(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        response = self.client.post(
            reverse("importer:sessions"),
            data={
                "entity_type": "lead",
                "source_format": "xlsx",
                "original_filename": "leads.xlsx",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["item"]["status"], "draft")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_create_session_does_not_require_csrf_cookie_for_bearer_flow(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            reverse("importer:sessions"),
            data={
                "entity_type": "lead",
                "source_format": "xlsx",
                "original_filename": "leads.xlsx",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["item"]["status"], "draft")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_create_smart_process_session_persists_entity_config(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        response = self.client.post(
            reverse("importer:sessions"),
            data={
                "entity_type": "smart_process",
                "source_format": "xlsx",
                "original_filename": "spa.xlsx",
                "entity_config": {
                    "entityTypeId": 128,
                    "title": "Согласования",
                },
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["item"]["status"], "draft")
        self.assertEqual(response.json()["item"]["entity_config"], {
            "entityTypeId": 128,
            "title": "Согласования",
        })

        session = ImportSession.objects.get(id=response.json()["item"]["id"])
        self.assertEqual(
            session.import_settings.get("entity_config"),
            {
                "entityTypeId": 128,
                "title": "Согласования",
            },
        )
