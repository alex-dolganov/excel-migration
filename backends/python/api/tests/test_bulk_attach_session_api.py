import json
import tempfile
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from importer.models import ImportSession
from importer.services.task_attachments import attach_file_to_crm_entity


def _make_account(**kwargs):
    defaults = dict(member_id="member-1", domain_url="test.bitrix24.ru", b24_user_id=7)
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class BulkAttachSessionCreateApiTest(TestCase):
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_create_session_persists_all_required_fields(self, get_from_jwt_token):
        get_from_jwt_token.return_value = _make_account()

        response = self.client.post(
            reverse("importer:bulk-attach-session-create"),
            data=json.dumps({
                "entity_type": "deal",
                "filter": {"STAGE_ID": "C1:NEW"},
                "file_id": "some-uuid",
                "field_id": "UF_CRM_PROMO_FILE",
            }),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertIn("item", body)
        self.assertEqual(body["item"]["status"], "draft")

        session = ImportSession.objects.get(id=body["item"]["id"])
        self.assertEqual(session.portal_member_id, "member-1")
        self.assertEqual(session.portal_domain, "test.bitrix24.ru")
        self.assertEqual(session.created_by_b24_user_id, 7)
        self.assertEqual(session.entity_type, "crm_files_deal")
        self.assertEqual(session.summary["bulk_attach"]["field_id"], "UF_CRM_PROMO_FILE")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_create_session_requires_file_url_or_file_id(self, get_from_jwt_token):
        get_from_jwt_token.return_value = _make_account()

        response = self.client.post(
            reverse("importer:bulk-attach-session-create"),
            data=json.dumps({
                "entity_type": "deal",
                "field_id": "UF_CRM_PROMO_FILE",
            }),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("file_url or file_id", response.json()["error"])

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_create_session_requires_field_id(self, get_from_jwt_token):
        get_from_jwt_token.return_value = _make_account()

        response = self.client.post(
            reverse("importer:bulk-attach-session-create"),
            data=json.dumps({
                "entity_type": "deal",
                "file_id": "some-uuid",
            }),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("field_id", response.json()["error"])

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_create_task_session_persists_task_attachment_entity_without_field_id(self, get_from_jwt_token):
        get_from_jwt_token.return_value = _make_account()

        response = self.client.post(
            reverse("importer:bulk-attach-session-create"),
            data=json.dumps({
                "entity_type": "task",
                "filter": {"STATUS": "2"},
                "file_id": "some-uuid",
                "file_name": "brief.pdf",
            }),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertIn("item", body)
        self.assertEqual(body["item"]["status"], "draft")

        session = ImportSession.objects.get(id=body["item"]["id"])
        self.assertEqual(session.entity_type, "task_attachment")
        self.assertEqual(session.source_format, "bulk_attach")
        self.assertEqual(
            session.summary["bulk_attach"],
            {
                "mode": "task",
                "entity_type": "task",
                "filter": {"STATUS": "2"},
                "file_url": "",
                "file_id": "some-uuid",
                "file_name": "brief.pdf",
            },
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_create_session_rejects_unsupported_entity_type(self, get_from_jwt_token):
        get_from_jwt_token.return_value = _make_account()

        response = self.client.post(
            reverse("importer:bulk-attach-session-create"),
            data=json.dumps({
                "entity_type": "project",
                "file_id": "some-uuid",
            }),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)


class BulkAttachPreviewApiTest(TestCase):
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_preview_accepts_task_entity_type(self, get_from_jwt_token):
        get_from_jwt_token.return_value = _make_account()

        response = self.client.post(
            reverse("importer:crm-filter-preview"),
            data=json.dumps({
                "entity_type": "task",
                "filter": {"STATUS": "2"},
            }),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.content)


class BulkAttachUploadApiTest(TestCase):
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_upload_saves_file_and_returns_file_id(self, get_from_jwt_token):
        get_from_jwt_token.return_value = _make_account()

        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media):
                file_data = BytesIO(b"fake pdf content")
                file_data.name = "promo.pdf"

                response = self.client.post(
                    reverse("importer:bulk-attach-upload"),
                    data={"file": file_data},
                    HTTP_AUTHORIZATION="Bearer test-token",
                )

        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertIn("file_id", body)
        self.assertIn("file_name", body)
        self.assertTrue(len(body["file_id"]) > 0)
        self.assertEqual(body["file_name"], "promo.pdf")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_upload_without_file_returns_400(self, get_from_jwt_token):
        get_from_jwt_token.return_value = _make_account()

        response = self.client.post(
            reverse("importer:bulk-attach-upload"),
            data={},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "File is required")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    @override_settings(BULK_ATTACH_MAX_FILE_SIZE_BYTES=4)
    def test_upload_rejects_file_over_bulk_attach_limit(self, get_from_jwt_token):
        get_from_jwt_token.return_value = _make_account()

        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media):
                file_data = BytesIO(b"way-too-big-for-a-4-byte-limit")
                file_data.name = "promo.pdf"

                response = self.client.post(
                    reverse("importer:bulk-attach-upload"),
                    data={"file": file_data},
                    HTTP_AUTHORIZATION="Bearer test-token",
                )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("МБ", response.json()["error"])

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    @override_settings(
        IMPORT_MAX_FILE_SIZE_BYTES=4,
        BULK_ATTACH_MAX_FILE_SIZE_BYTES=150 * 1024 * 1024,
    )
    def test_upload_allows_file_larger_than_spreadsheet_import_limit(self, get_from_jwt_token):
        # Bulk attach has its own (larger) limit; a file over the 4-byte spreadsheet
        # import limit must still be accepted because the bulk limit is 150 MB.
        get_from_jwt_token.return_value = _make_account()

        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media):
                file_data = BytesIO(b"larger-than-the-4-byte-spreadsheet-limit")
                file_data.name = "promo.pdf"

                response = self.client.post(
                    reverse("importer:bulk-attach-upload"),
                    data={"file": file_data},
                    HTTP_AUTHORIZATION="Bearer test-token",
                )

        self.assertEqual(response.status_code, 200, response.content)


class AttachFileToCrmEntityTest(TestCase):
    @patch("importer.services.task_attachments.BitrixAPIRequest")
    def test_actually_calls_bitrix_api(self, MockRequest):
        """Проверяет что .result доступается (API вызывается), а не просто создаётся объект."""
        mock_instance = MagicMock()
        result_prop = PropertyMock(return_value=True)
        type(mock_instance).result = result_prop
        MockRequest.return_value = mock_instance

        account = _make_account()
        attach_file_to_crm_entity(
            account,
            entity_type="crm_files_deal",
            record_id=42,
            field_id="UF_CRM_PROMO_FILE",
            file_name="test.pdf",
            content=b"fake content",
        )

        result_prop.assert_called_once()  # .result был вызван => API реально выполнился
        call_kwargs = MockRequest.call_args.kwargs
        self.assertEqual(call_kwargs["api_method"], "crm.deal.update")
        self.assertEqual(call_kwargs["params"]["id"], 42)
        self.assertIn("UF_CRM_PROMO_FILE", call_kwargs["params"]["fields"])
        file_data = call_kwargs["params"]["fields"]["UF_CRM_PROMO_FILE"]
        self.assertIn("fileData", file_data)
        self.assertEqual(file_data["fileData"][0], "test.pdf")

    @patch("importer.services.task_attachments.BitrixAPIRequest")
    def test_raises_on_bitrix_api_error(self, MockRequest):
        """Если Bitrix24 вернул ошибку (KeyError на result) — исключение пробрасывается."""
        mock_instance = MagicMock()
        result_prop = PropertyMock(side_effect=KeyError("result"))
        type(mock_instance).result = result_prop
        MockRequest.return_value = mock_instance

        account = _make_account()
        with self.assertRaises(Exception):
            attach_file_to_crm_entity(
                account,
                entity_type="crm_files_deal",
                record_id=42,
                field_id="UF_CRM_PROMO_FILE",
                file_name="test.pdf",
                content=b"fake content",
            )
