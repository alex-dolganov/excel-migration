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
