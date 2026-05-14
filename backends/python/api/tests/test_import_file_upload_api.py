import shutil
import tempfile
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from importer.models import ImportSession


class ImportFileUploadApiTest(TestCase):
    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_upload_file_updates_session_metadata(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.DRAFT,
            original_filename="draft.xlsx",
        )

        upload = SimpleUploadedFile(
            "leads.xlsx",
            b"PK\x03\x04fake-xlsx-content",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        response = self.client.post(
            reverse("importer:session-upload", kwargs={"session_id": session.id}),
            data={"file": upload},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)

        session.refresh_from_db()
        self.assertEqual(session.status, ImportSession.Status.UPLOADED)
        self.assertEqual(session.original_filename, "leads.xlsx")
        self.assertEqual(session.file_size_bytes, len(b"PK\x03\x04fake-xlsx-content"))
        self.assertTrue(session.stored_file.name.endswith(".xlsx"))

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_upload_requires_file(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.DRAFT,
            original_filename="draft.xlsx",
        )

        response = self.client.post(
            reverse("importer:session-upload", kwargs={"session_id": session.id}),
            data={},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "File is required")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    @patch("importer.views.get_max_import_file_size_megabytes", return_value=1)
    @patch("importer.views.get_max_import_file_size_bytes", return_value=4)
    def test_upload_rejects_files_larger_than_50_mb(
        self,
        get_max_import_file_size_bytes,
        get_max_import_file_size_megabytes,
        get_from_jwt_token,
    ):
        del get_max_import_file_size_bytes
        del get_max_import_file_size_megabytes
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.DRAFT,
            original_filename="draft.xlsx",
        )

        upload = SimpleUploadedFile(
            "huge.xlsx",
            b"PK\x03\x04x",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        response = self.client.post(
            reverse("importer:session-upload", kwargs={"session_id": session.id}),
            data={"file": upload},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Файл слишком большой. Максимум для импорта — 1 МБ.")

        session.refresh_from_db()
        self.assertEqual(session.status, ImportSession.Status.DRAFT)
        self.assertEqual(session.file_size_bytes, None)
        self.assertFalse(session.stored_file)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_upload_is_limited_to_current_portal_session(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        foreign_session = ImportSession.objects.create(
            portal_member_id="member-2",
            portal_domain="other.bitrix24.ru",
            created_by_b24_user_id=99,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.DRAFT,
            original_filename="foreign.xlsx",
        )

        upload = SimpleUploadedFile(
            "leads.xlsx",
            b"fake-xlsx-content",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        response = self.client.post(
            reverse("importer:session-upload", kwargs={"session_id": foreign_session.id}),
            data={"file": upload},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 404)
