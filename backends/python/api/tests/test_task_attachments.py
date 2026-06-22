import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

from django.test import SimpleTestCase

from importer.services.task_attachments import _validate_url_for_ssrf, attach_file_to_task, download_attachment_source


class _AttachmentDownloadHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/final")
            self.end_headers()
            return

        if self.path == "/final":
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return


class DownloadAttachmentSourceSecurityTest(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _AttachmentDownloadHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self._base_url = f"http://127.0.0.1:{self._server.server_port}"

    def tearDown(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)
        super().tearDown()

    @patch("importer.services.task_attachments._validate_url_for_ssrf")
    def test_download_attachment_source_rejects_redirect_responses(self, validate_url_for_ssrf):
        validate_url_for_ssrf.return_value = None

        with self.assertRaisesRegex(ValueError, "Укажите прямую ссылку на файл без перенаправлений"):
            download_attachment_source(f"{self._base_url}/redirect")

    @patch("importer.services.task_attachments._validate_url_for_ssrf")
    def test_download_attachment_source_downloads_direct_response(self, validate_url_for_ssrf):
        validate_url_for_ssrf.return_value = None

        result = download_attachment_source(f"{self._base_url}/final")

        self.assertEqual(result["content"], b"ok")
        self.assertEqual(result["file_name"], "final")
        self.assertEqual(result["content_type"], "text/plain")

    def test_validate_url_for_ssrf_rejects_unsupported_scheme_with_clear_message(self):
        with self.assertRaisesRegex(ValueError, "Используйте только http или https"):
            _validate_url_for_ssrf("ftp://files.example.com/test.txt")

    @patch("importer.services.task_attachments.socket.getaddrinfo")
    def test_validate_url_for_ssrf_rejects_private_address_with_clear_message(self, getaddrinfo):
        getaddrinfo.return_value = [
            (2, 1, 6, "", ("127.0.0.1", 80)),
        ]

        with self.assertRaisesRegex(ValueError, "локальный или внутренний адрес"):
            _validate_url_for_ssrf("http://files.example.com/test.txt")


class AttachFileToTaskTest(SimpleTestCase):
    @patch("importer.services.task_attachments.BitrixAPIRequest")
    def test_attach_file_to_task_uploads_file_to_user_storage_before_attaching_to_task(self, MockRequest):
        storage_request = MagicMock()
        type(storage_request).result = PropertyMock(
            return_value=[
                {
                    "ID": "13",
                    "ENTITY_TYPE": "user",
                    "ENTITY_ID": "7",
                    "ROOT_OBJECT_ID": "21",
                }
            ]
        )

        upload_request = MagicMock()
        type(upload_request).result = PropertyMock(
            return_value={
                "ID": 6687,
                "FILE_ID": 28073,
            }
        )

        attach_request = MagicMock()
        attach_result_prop = PropertyMock(return_value={"attachmentId": 7001})
        type(attach_request).result = attach_result_prop

        MockRequest.side_effect = [storage_request, upload_request, attach_request]

        account = SimpleNamespace(member_id="member-1", domain_url="test.bitrix24.ru", b24_user_id=7)

        result = attach_file_to_task(
            account,
            task_id=801,
            file_name="brief.txt",
            content=b"hello world",
            content_type="text/plain",
        )

        attach_result_prop.assert_called_once()
        self.assertEqual(result, {"attachmentId": 7001})
        self.assertEqual(MockRequest.call_count, 3)

        storage_call = MockRequest.call_args_list[0].kwargs
        self.assertEqual(storage_call["api_method"], "disk.storage.getlist")

        upload_call = MockRequest.call_args_list[1].kwargs
        self.assertEqual(upload_call["api_method"], "disk.storage.uploadfile")
        self.assertEqual(upload_call["params"]["id"], 13)
        self.assertEqual(upload_call["params"]["data"]["NAME"], "brief.txt")
        self.assertEqual(upload_call["params"]["fileContent"][0], "brief.txt")
        self.assertTrue(upload_call["params"]["generateUniqueName"])

        attach_call = MockRequest.call_args_list[2].kwargs
        self.assertEqual(attach_call["api_method"], "tasks.task.files.attach")
        self.assertEqual(attach_call["params"]["taskId"], 801)
        self.assertEqual(attach_call["params"]["fileId"], 6687)

    @patch("importer.services.task_attachments.BitrixAPIRequest")
    def test_attach_file_to_task_propagates_error_without_legacy_fallback(self, MockRequest):
        # Современный путь (Диск + tasks.task.files.attach) без legacy-отката:
        # ошибка загрузки на Диск пробрасывается, а не уходит в task.item.addfile.
        storage_request = MagicMock()
        type(storage_request).result = PropertyMock(
            side_effect=Exception("The request requires higher privileges than provided by the access token")
        )
        MockRequest.side_effect = [storage_request]

        account = SimpleNamespace(member_id="member-1", domain_url="test.bitrix24.ru", b24_user_id=7)

        with self.assertRaises(Exception):
            attach_file_to_task(
                account,
                task_id=801,
                file_name="brief.txt",
                content=b"hello world",
                content_type="text/plain",
            )

        called_methods = [call.kwargs["api_method"] for call in MockRequest.call_args_list]
        self.assertNotIn("task.item.addfile", called_methods)
