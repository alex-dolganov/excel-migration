import base64
from pathlib import PurePosixPath
from urllib.parse import urlparse
from urllib.request import urlopen

from b24pysdk.bitrix_api.requests import BitrixAPIRequest


def _fallback_file_name_from_url(file_url: str) -> str:
    parsed_path = PurePosixPath(urlparse(file_url).path or "")
    return parsed_path.name or "attachment.bin"


def download_attachment_source(file_url: str) -> dict:
    with urlopen(file_url) as response:
        content = response.read()
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
