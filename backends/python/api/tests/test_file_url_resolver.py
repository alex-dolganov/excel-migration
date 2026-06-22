"""Unit tests for importer.services.file_url_resolver."""
import json
from io import BytesIO
from unittest import TestCase
from unittest.mock import MagicMock, patch

from importer.services.file_url_resolver import (
    FileUrlResolutionError,
    resolve_download_url,
)


class ResolveDownloadUrlDirectTest(TestCase):
    """Direct (non-cloud) URLs pass through unchanged."""

    def test_direct_http_url(self):
        url = "http://example.com/file.pdf"
        self.assertEqual(resolve_download_url(url), url)

    def test_direct_https_url(self):
        url = "https://example.com/report.xlsx"
        self.assertEqual(resolve_download_url(url), url)

    def test_empty_string(self):
        self.assertEqual(resolve_download_url(""), "")

    def test_none_value(self):
        self.assertEqual(resolve_download_url(None), None)

    def test_unknown_provider(self):
        url = "https://storage.somecloud.io/files/doc.docx"
        self.assertEqual(resolve_download_url(url), url)


class ResolveGoogleDriveTest(TestCase):
    def test_file_path_pattern(self):
        share_url = "https://drive.google.com/file/d/1ABC_xyz-123/view?usp=sharing"
        result = resolve_download_url(share_url)
        self.assertEqual(result, "https://drive.google.com/uc?export=download&id=1ABC_xyz-123")

    def test_open_id_pattern(self):
        share_url = "https://drive.google.com/open?id=1ABC_xyz-123"
        result = resolve_download_url(share_url)
        self.assertEqual(result, "https://drive.google.com/uc?export=download&id=1ABC_xyz-123")

    def test_docs_subdomain(self):
        share_url = "https://docs.google.com/file/d/1XYZ456/view"
        result = resolve_download_url(share_url)
        self.assertEqual(result, "https://drive.google.com/uc?export=download&id=1XYZ456")

    def test_unrecognized_google_url_passthrough(self):
        share_url = "https://drive.google.com/drive/folders/someFolder"
        self.assertEqual(resolve_download_url(share_url), share_url)


class ResolveDropboxTest(TestCase):
    def test_dl0_replaced_with_dl1(self):
        share_url = "https://www.dropbox.com/s/abc123/myfile.pdf?dl=0"
        result = resolve_download_url(share_url)
        self.assertIn("dl=1", result)
        self.assertNotIn("dl=0", result)

    def test_no_dl_param_adds_dl1(self):
        share_url = "https://dropbox.com/s/abc123/myfile.pdf"
        result = resolve_download_url(share_url)
        self.assertIn("dl=1", result)

    def test_dl1_unchanged(self):
        share_url = "https://www.dropbox.com/s/abc123/myfile.pdf?dl=1"
        result = resolve_download_url(share_url)
        self.assertIn("dl=1", result)
        self.assertNotIn("dl=0", result)


class ResolveOnedriveTest(TestCase):
    def test_adds_download_param(self):
        share_url = "https://1drv.ms/b/s!AbCdEfGhIj"
        result = resolve_download_url(share_url)
        self.assertIn("download=1", result)

    def test_onedrive_live_adds_download(self):
        share_url = "https://onedrive.live.com/redir?resid=AAAA"
        result = resolve_download_url(share_url)
        self.assertIn("download=1", result)

    def test_existing_download_param_not_duplicated(self):
        share_url = "https://1drv.ms/b/s!AbCdEfGhIj?download=1"
        result = resolve_download_url(share_url)
        self.assertEqual(result.count("download=1"), 1)


class ResolveYandexDiskTest(TestCase):
    def _mock_yandex_response(self, href):
        response_body = json.dumps({"href": href, "method": "GET"}).encode("utf-8")
        mock_response = MagicMock()
        mock_response.read.return_value = response_body
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        return mock_response

    def test_yandex_disk_resolved(self):
        direct_url = "https://downloader.disk.yandex.ru/disk/path/file.pdf?token=abc"
        with patch("importer.services.file_url_resolver.urllib.request.urlopen") as mock_open:
            mock_open.return_value = self._mock_yandex_response(direct_url)
            result = resolve_download_url("https://disk.yandex.ru/i/someShareId")
        self.assertEqual(result, direct_url)

    def test_yadi_sk_resolved(self):
        direct_url = "https://downloader.disk.yandex.ru/disk/path/photo.jpg?token=xyz"
        with patch("importer.services.file_url_resolver.urllib.request.urlopen") as mock_open:
            mock_open.return_value = self._mock_yandex_response(direct_url)
            result = resolve_download_url("https://yadi.sk/d/shortId")
        self.assertEqual(result, direct_url)

    def test_yandex_api_error_raises(self):
        with patch("importer.services.file_url_resolver.urllib.request.urlopen") as mock_open:
            mock_open.side_effect = Exception("Connection refused")
            with self.assertRaises(FileUrlResolutionError):
                resolve_download_url("https://disk.yandex.ru/i/someId")

    def test_yandex_missing_href_raises(self):
        response_body = json.dumps({"error": "DiskNotFoundError"}).encode("utf-8")
        mock_response = MagicMock()
        mock_response.read.return_value = response_body
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        with patch("importer.services.file_url_resolver.urllib.request.urlopen") as mock_open:
            mock_open.return_value = mock_response
            with self.assertRaises(FileUrlResolutionError):
                resolve_download_url("https://disk.yandex.com/i/privateFile")
