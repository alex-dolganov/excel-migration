import base64
import ipaddress
import re
import socket
from pathlib import PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import HTTPRedirectHandler, build_opener

from b24pysdk.bitrix_api.requests import BitrixAPIRequest

from .file_url_resolver import resolve_download_url

_ALLOWED_SCHEMES = {"http", "https"}
_MAX_ATTACHMENT_SIZE = 20 * 1024 * 1024  # 20 MB
_DOWNLOAD_TIMEOUT = 15  # seconds
_UNSUPPORTED_SCHEME_ERROR = "Ссылка на файл использует неподдерживаемый протокол. Используйте только http или https."
_MISSING_HOST_ERROR = "В ссылке на файл не указан адрес сайта."
_HOST_RESOLUTION_ERROR = "Не удалось открыть ссылку на файл: адрес сайта не найден."
_FORBIDDEN_ADDRESS_ERROR = "Ссылка на файл ведёт на локальный или внутренний адрес. Используйте внешнюю публичную ссылку."
_EMPTY_DOWNLOAD_ERROR = "Файл по ссылке пустой."


_CONTENT_DISPOSITION_FILENAME_RE = re.compile(
    r"filename\*?=(?:UTF-8'')?[\"']?([^\"';\r\n]+)[\"']?",
    re.IGNORECASE,
)


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            _validate_url_for_ssrf(newurl)
        except ValueError:
            return None  # block redirects to private/internal addresses
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fallback_file_name_from_url(file_url: str) -> str:
    parsed_path = PurePosixPath(urlparse(file_url).path or "")
    return parsed_path.name or "attachment.bin"


def _extract_filename_from_disposition(header: str) -> str:
    if not header:
        return ""
    match = _CONTENT_DISPOSITION_FILENAME_RE.search(header)
    if not match:
        return ""
    name = match.group(1).strip().strip("\"'")
    try:
        name = unquote(name)
    except Exception:
        pass
    return name or ""


def _validate_url_for_ssrf(file_url: str) -> None:
    parsed = urlparse(file_url)

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(_UNSUPPORTED_SCHEME_ERROR)

    hostname = parsed.hostname
    if not hostname:
        raise ValueError(_MISSING_HOST_ERROR)

    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError(_HOST_RESOLUTION_ERROR) from exc

    for _family, _type, _proto, _canonname, sockaddr in addr_infos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError(_FORBIDDEN_ADDRESS_ERROR)


def download_attachment_source(file_url: str) -> dict:
    resolved_url = resolve_download_url(file_url)
    _validate_url_for_ssrf(resolved_url)

    opener = build_opener(_SafeRedirectHandler)
    try:
        with opener.open(resolved_url, timeout=_DOWNLOAD_TIMEOUT) as response:
            content = response.read(_MAX_ATTACHMENT_SIZE)
            content_type = response.headers.get_content_type() if response.headers else ""
            disposition = (response.headers.get("Content-Disposition") or "") if response.headers else ""
    except HTTPError as error:
        raise ValueError(f"Не удалось скачать файл по ссылке: сервер вернул HTTP {error.code}.") from error
    except URLError as error:
        raise ValueError("Не удалось скачать файл по ссылке. Проверьте, что ссылка доступна извне.") from error

    if not content:
        raise ValueError(_EMPTY_DOWNLOAD_ERROR)

    file_name = (
        _extract_filename_from_disposition(disposition)
        or _fallback_file_name_from_url(resolved_url)
        or _fallback_file_name_from_url(file_url)
    )
    return {
        "content": content,
        "file_name": file_name,
        "content_type": content_type or "application/octet-stream",
    }


def _unwrap_bitrix_result(request):
    direct_result = getattr(request, "result", None)
    if direct_result is not None:
        return direct_result

    api_response = getattr(request, "response", None)
    if api_response is not None and hasattr(api_response, "result"):
        return getattr(api_response, "result")
    return None


def _normalize_bitrix_items(result) -> list[dict]:
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if isinstance(result, dict):
        for key in ("items", "result"):
            items = result.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
    return []


def _extract_int_value(payload, *keys: str) -> int | None:
    if not isinstance(payload, dict):
        return None

    for key in keys:
        raw_value = payload.get(key)
        if raw_value in (None, ""):
            continue
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            continue
    return None


def _is_insufficient_scope_error(error: Exception) -> bool:
    normalized_message = str(error or "").strip().lower()
    return "higher privileges than provided by the access token" in normalized_message


def _resolve_task_attachment_storage_id(account) -> int:
    user_id = int(getattr(account, "b24_user_id", 0) or 0)
    if user_id <= 0:
        raise ValueError("Не удалось определить Bitrix-пользователя для загрузки вложения в задачу.")

    request = BitrixAPIRequest(
        bitrix_token=account,
        api_method="disk.storage.getlist",
        params={
            "filter": {
                "ENTITY_TYPE": "user",
                "ENTITY_ID": user_id,
            }
        },
    )
    storage_items = _normalize_bitrix_items(_unwrap_bitrix_result(request))
    if not storage_items:
        raise ValueError("Не удалось найти Bitrix Disk-хранилище пользователя для вложения в задачу.")

    for storage_item in storage_items:
        storage_id = _extract_int_value(storage_item, "ID", "id")
        if storage_id is not None:
            return storage_id

    raise ValueError("Bitrix Disk вернул хранилище без идентификатора.")


def _upload_file_to_task_storage(account, *, storage_id: int, file_name: str, content: bytes):
    encoded = base64.b64encode(content).decode("utf-8")
    request = BitrixAPIRequest(
        bitrix_token=account,
        api_method="disk.storage.uploadfile",
        params={
            "id": storage_id,
            "data": {
                "NAME": file_name,
            },
            "fileContent": [file_name, encoded],
            "generateUniqueName": True,
        },
    )
    upload_result = _unwrap_bitrix_result(request)
    if not isinstance(upload_result, dict):
        raise ValueError("Bitrix Disk не вернул данные о загруженном файле.")

    file_id = _extract_int_value(upload_result, "ID", "id")
    if file_id is None:
        raise ValueError("Bitrix Disk не вернул идентификатор загруженного файла.")

    return file_id


def _attach_file_to_task_legacy(account, *, task_id: int, file_name: str, content: bytes):
    encoded = base64.b64encode(content).decode("utf-8")
    request = BitrixAPIRequest(
        bitrix_token=account,
        api_method="task.item.addfile",
        params={
            "TASK_ID": task_id,
            "FILE": {
                "NAME": file_name,
                "CONTENT": encoded,
            },
        },
    )
    return request.result


def attach_file_to_task(account, *, task_id: int, file_name: str, content: bytes, content_type: str = ""):
    try:
        storage_id = _resolve_task_attachment_storage_id(account)
        file_id = _upload_file_to_task_storage(
            account,
            storage_id=storage_id,
            file_name=file_name,
            content=content,
        )
        request = BitrixAPIRequest(
            bitrix_token=account,
            api_method="tasks.task.files.attach",
            params={
                "taskId": task_id,
                "fileId": file_id,
            },
        )
        return request.result
    except Exception as error:
        if not _is_insufficient_scope_error(error):
            raise
        return _attach_file_to_task_legacy(
            account,
            task_id=task_id,
            file_name=file_name,
            content=content,
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
    request = BitrixAPIRequest(
        bitrix_token=account,
        api_method=api_method,
        params={
            "id": record_id,
            "fields": {field_id: {"fileData": [file_name, encoded]}},
        },
    )
    return request.result


_CRM_UF_FILE_UPDATE_METHODS = {
    "lead": "crm.lead.update",
    "contact": "crm.contact.update",
    "company": "crm.company.update",
    "deal": "crm.deal.update",
}


def attach_uf_file_field(
    account,
    *,
    entity_type: str,
    record_id: int,
    field_id: str,
    field_type: str,
    file_url: str,
    entity_type_id: int | None = None,
):
    """Download a file and attach it to a UF_ file field on a CRM record.

    field_type "file":      Base64 via crm.*.update → {"fileData": [name, b64]}
    field_type "disk_file": upload to user Drive → crm.*.update → "n{drive_id}"
    """
    download_result = download_attachment_source(file_url)
    content: bytes = download_result["content"]
    file_name: str = download_result["file_name"]

    if field_type == "disk_file":
        storage_id = _resolve_task_attachment_storage_id(account)
        file_id = _upload_file_to_task_storage(
            account,
            storage_id=storage_id,
            file_name=file_name,
            content=content,
        )
        file_payload = f"n{file_id}"
    elif entity_type == "smart_process":
        # crm.item.update expects [filename, base64] array, not {"fileData": [...]}
        encoded = base64.b64encode(content).decode("utf-8")
        file_payload = [file_name, encoded]
    else:
        encoded = base64.b64encode(content).decode("utf-8")
        file_payload = {"fileData": [file_name, encoded]}

    if entity_type == "smart_process":
        if not entity_type_id:
            raise ValueError("entityTypeId is required for smart_process UF file field attachment.")
        request = BitrixAPIRequest(
            bitrix_token=account,
            api_method="crm.item.update",
            params={
                "entityTypeId": entity_type_id,
                "id": record_id,
                "fields": {field_id: file_payload},
            },
        )
    else:
        api_method = _CRM_UF_FILE_UPDATE_METHODS.get(str(entity_type or ""))
        if not api_method:
            raise ValueError(f"UF file field attachment not supported for entity type: {entity_type}")
        request = BitrixAPIRequest(
            bitrix_token=account,
            api_method=api_method,
            params={
                "id": record_id,
                "fields": {field_id: file_payload},
            },
        )
    return request.result
