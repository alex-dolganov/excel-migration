import os

from b24pysdk.bitrix_api.requests import BitrixAPIRequest
from django.conf import settings

from importer.models import ImportSession

from .task_attachments import attach_file_to_task, download_attachment_source


TASK_LIST_SELECT = ["ID", "TITLE"]
BULK_ATTACH_PROGRESS_INTERVAL = 10


def _normalize_task_list_result(result) -> list[dict]:
    if isinstance(result, dict):
        for key in ("tasks", "items", "result"):
            items = result.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        return []

    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]

    return []


def _extract_task_title(item: dict) -> str:
    return str(
        item.get("TITLE")
        or item.get("title")
        or item.get("NAME")
        or item.get("name")
        or item.get("ID")
        or item.get("id")
        or ""
    ).strip()


def fetch_task_entities_page(account, filter_params: dict, start: int = 0) -> dict:
    request = BitrixAPIRequest(
        bitrix_token=account,
        api_method="tasks.task.list",
        params={
            "filter": filter_params or {},
            "select": TASK_LIST_SELECT,
            "start": start,
        },
    )
    api_response = getattr(request, "response", request)
    items = [
        {
            "id": str(item.get("ID") or item.get("id") or "").strip(),
            "title": _extract_task_title(item),
        }
        for item in _normalize_task_list_result(getattr(api_response, "result", None))
    ]

    total = getattr(api_response, "total", None)
    next_start = getattr(api_response, "next", None)

    return {
        "items": [item for item in items if item["id"]],
        "total": int(total) if total is not None else len(items),
        "next": int(next_start) if next_start is not None else None,
    }


def fetch_task_ids(account, filter_params: dict) -> list[int]:
    all_ids = []
    start = 0

    while True:
        page = fetch_task_entities_page(account, filter_params, start=start)
        for item in page["items"]:
            raw_id = item.get("id")
            if raw_id is None:
                continue
            try:
                all_ids.append(int(raw_id))
            except (TypeError, ValueError):
                continue

        next_start = page.get("next")
        if next_start is None:
            break
        start = next_start

    return all_ids


def _load_bulk_attach_source(*, bulk_config: dict) -> tuple[bytes, str]:
    file_id = str(bulk_config.get("file_id") or "").strip()
    file_url = str(bulk_config.get("file_url") or "").strip()
    file_name_override = str(bulk_config.get("file_name") or "").strip()

    if file_id:
        upload_dir = os.path.join(settings.MEDIA_ROOT, "bulk-attach-uploads", file_id)
        try:
            file_entries = os.listdir(upload_dir)
        except OSError as error:
            raise ValueError(f"Загруженный файл не найден: {error}")
        if not file_entries:
            raise ValueError("Загруженный файл не найден (пустая директория)")

        disk_file_name = file_entries[0]
        with open(os.path.join(upload_dir, disk_file_name), "rb") as fh:
            return fh.read(), file_name_override or disk_file_name

    if not file_url:
        raise ValueError("Bulk attach config is incomplete (file_url or file_id is required)")

    download_result = download_attachment_source(file_url)
    return download_result.get("content") or b"", file_name_override or download_result.get("file_name") or "attachment.bin"


def execute_task_bulk_attach(*, session, account) -> dict:
    bulk_config = (session.summary or {}).get("bulk_attach", {})
    if str(bulk_config.get("mode") or "").strip() != "task":
        raise ValueError("Session is not configured for task bulk attach")

    filter_params = bulk_config.get("filter") or {}
    if not isinstance(filter_params, dict):
        filter_params = {}

    task_ids = fetch_task_ids(account, filter_params)
    total = len(task_ids)

    session.total_rows = total
    session.processed_rows = 0
    session.successful_rows = 0
    session.failed_rows = 0
    session.save(update_fields=["total_rows", "processed_rows", "successful_rows", "failed_rows", "updated_at"])

    if total == 0:
        session.status = ImportSession.Status.COMPLETED
        session.save(update_fields=["status", "updated_at"])
        return {"total": 0, "successful": 0, "failed": 0, "results": []}

    content, resolved_file_name = _load_bulk_attach_source(bulk_config=bulk_config)

    results = []
    successful = 0
    failed = 0

    for index, task_id in enumerate(task_ids):
        if session.status == ImportSession.Status.CANCELLED:
            break

        try:
            attach_file_to_task(
                account,
                task_id=task_id,
                file_name=resolved_file_name,
                content=content,
            )
            successful += 1
            results.append({"entity_id": task_id, "status": "success"})
        except Exception as error:
            failed += 1
            results.append({"entity_id": task_id, "status": "failed", "error": str(error)})

        if (index + 1) % BULK_ATTACH_PROGRESS_INTERVAL == 0:
            session.processed_rows = index + 1
            session.successful_rows = successful
            session.failed_rows = failed
            session.save(update_fields=["processed_rows", "successful_rows", "failed_rows", "updated_at"])
            session.refresh_from_db(fields=["status"])

    session.processed_rows = len(results)
    session.successful_rows = successful
    session.failed_rows = failed
    session.save(update_fields=["processed_rows", "successful_rows", "failed_rows", "updated_at"])

    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "results": results,
    }
