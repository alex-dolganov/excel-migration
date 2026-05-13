import base64
import ipaddress
import socket
from pathlib import PurePosixPath
from urllib.parse import urlparse
from urllib.request import urlopen

from b24pysdk.bitrix_api.requests import BitrixAPIRequest

_ALLOWED_SCHEMES = {"http", "https"}
_MAX_ATTACHMENT_SIZE = 20 * 1024 * 1024  # 20 MB
_DOWNLOAD_TIMEOUT = 15  # seconds


def _fallback_file_name_from_url(file_url: str) -> str:
    parsed_path = PurePosixPath(urlparse(file_url).path or "")
    return parsed_path.name or "attachment.bin"


def _validate_url_for_ssrf(file_url: str) -> None:
    parsed = urlparse(file_url)

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"Недопустимая схема URL: {parsed.scheme!r}. Разрешены только http и https")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL не содержит хоста")

    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"Не удалось разрешить хост '{hostname}'") from exc

    for _family, _type, _proto, _canonname, sockaddr in addr_infos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError(f"URL указывает на запрещённый сетевой адрес")


def download_attachment_source(file_url: str) -> dict:
    _validate_url_for_ssrf(file_url)

    with urlopen(file_url, timeout=_DOWNLOAD_TIMEOUT) as response:
        content = response.read(_MAX_ATTACHMENT_SIZE)
        content_type = response.headers.get_content_type() if response.headers else ""

    if not content:
        raise ValueError("Downloaded attachment is empty")

    return {
        "content": content,
        "file_name": _fallback_file_name_from_url(file_url),
        "content_type": content_type or "application/octet-stream",
    }


def attach_file_to_task(account, *, task_id: int, file_name: str, content: bytes, content_type: str = ""):
    encoded = base64.b64encode(content).decode("utf-8")
    return BitrixAPIRequest(
        bitrix_token=account,
        api_method="tasks.task.files.attach",
        params={
            "taskId": task_id,
            "file": [file_name, encoded],
        },
    )


_CRM_UPDATE_API_METHODS = {
    "crm_files_lead": "crm.lead.update",
    "crm_files_contact": "crm.contact.update",
    "crm_files_company": "crm.company.update",
    "crm_files_deal": "crm.deal.update",
}


def attach_file_to_crm_entity(account, *, entity_type: str, record_id: int, field_id: str, file_name: str, content: bytes):
    api_method = _CRM_UPDATE_API_METHODS.get(str(entity_type or ""))
    if not api_method:
        raise ValueError(f"Unsupported CRM file entity type: {entity_type}")

    encoded = base64.b64encode(content).decode("utf-8")
    return BitrixAPIRequest(
        bitrix_token=account,
        api_method=api_method,
        params={
            "id": record_id,
            "fields": {field_id: {"fileData": [file_name, encoded]}},
        },
    )
