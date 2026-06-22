import json
import re
import urllib.parse
import urllib.request

_YANDEX_DISK_DOMAINS = {"disk.yandex.ru", "disk.yandex.com", "yadi.sk"}
_GOOGLE_DRIVE_DOMAINS = {"drive.google.com", "docs.google.com"}
_DROPBOX_DOMAINS = {"www.dropbox.com", "dropbox.com"}
_ONEDRIVE_DOMAINS = {"1drv.ms", "onedrive.live.com", "onedrive.com"}

_GOOGLE_DRIVE_FILE_RE = re.compile(r"/file/d/([a-zA-Z0-9_-]+)")

_YANDEX_API_BASE = "https://cloud-api.yandex.net/v1/disk/public/resources/download"
_RESOLVE_TIMEOUT = 10  # seconds


class FileUrlResolutionError(ValueError):
    pass


def resolve_download_url(url: str) -> str:
    """Convert a cloud storage share URL to a direct download URL.

    Returns the original URL unchanged for direct links or unsupported providers.
    Raises FileUrlResolutionError if a supported provider returns an error.
    """
    if not url or not isinstance(url, str):
        return url

    parsed = urllib.parse.urlparse(url)
    hostname = (parsed.hostname or "").lower()

    if hostname in _YANDEX_DISK_DOMAINS:
        return _resolve_yandex_disk(url)

    if hostname in _GOOGLE_DRIVE_DOMAINS:
        return _resolve_google_drive(url, parsed)

    if hostname in _DROPBOX_DOMAINS:
        return _resolve_dropbox(url, parsed)

    if hostname in _ONEDRIVE_DOMAINS:
        return _resolve_onedrive(url, parsed)

    return url


def _resolve_yandex_disk(share_url: str) -> str:
    api_url = "{}?public_key={}".format(
        _YANDEX_API_BASE,
        urllib.parse.quote(share_url, safe=""),
    )
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=_RESOLVE_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise FileUrlResolutionError(
            f"Не удалось получить ссылку на скачивание с Яндекс Диска: {exc}"
        ) from exc

    href = data.get("href") if isinstance(data, dict) else None
    if not href:
        raise FileUrlResolutionError(
            "Яндекс Диск не вернул ссылку для скачивания. "
            "Убедитесь, что файл открыт для общего доступа."
        )
    return href


def _resolve_google_drive(share_url: str, parsed: urllib.parse.ParseResult) -> str:
    # Pattern: /file/d/{ID}/...
    path_match = _GOOGLE_DRIVE_FILE_RE.search(parsed.path)
    if path_match:
        return f"https://drive.google.com/uc?export=download&id={path_match.group(1)}"

    # Pattern: ?id={ID} or open?id={ID}
    qs_params = urllib.parse.parse_qs(parsed.query or "", keep_blank_values=True)
    file_id = (qs_params.get("id") or [None])[0]
    if file_id:
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    return share_url


def _resolve_dropbox(share_url: str, parsed: urllib.parse.ParseResult) -> str:
    params = urllib.parse.parse_qs(parsed.query or "", keep_blank_values=True)
    params["dl"] = ["1"]
    new_query = urllib.parse.urlencode(
        {k: v[0] for k, v in params.items()}, quote_via=urllib.parse.quote
    )
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


def _resolve_onedrive(share_url: str, parsed: urllib.parse.ParseResult) -> str:
    params = urllib.parse.parse_qs(parsed.query or "", keep_blank_values=True)
    if "download" not in params:
        params["download"] = ["1"]
        new_query = urllib.parse.urlencode(
            {k: v[0] for k, v in params.items()}, quote_via=urllib.parse.quote
        )
        return urllib.parse.urlunparse(parsed._replace(query=new_query))
    return share_url
