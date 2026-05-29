import os
import time

from b24pysdk.bitrix_api.requests import BitrixAPIRequest

from .task_attachments import attach_file_to_crm_entity, download_attachment_source


CRM_LIST_METHODS = {
    "lead": "crm.lead.list",
    "contact": "crm.contact.list",
    "company": "crm.company.list",
    "deal": "crm.deal.list",
}

CRM_FILES_ENTITY_TYPES = {
    "lead": "crm_files_lead",
    "contact": "crm_files_contact",
    "company": "crm_files_company",
    "deal": "crm_files_deal",
}

_CRM_TITLE_SELECT = {
    "lead": ["ID", "TITLE"],
    "contact": ["ID", "NAME", "LAST_NAME"],
    "company": ["ID", "TITLE"],
    "deal": ["ID", "TITLE"],
}

SUPPORTED_ENTITY_TYPES = set(CRM_LIST_METHODS.keys())
BULK_ATTACH_PROGRESS_INTERVAL = 10


def _extract_entity_title(entity_type: str, item: dict) -> str:
    if entity_type == "contact":
        parts = [str(item.get("NAME") or ""), str(item.get("LAST_NAME") or "")]
        return " ".join(p for p in parts if p).strip() or str(item.get("ID", ""))
    return str(item.get("TITLE") or item.get("NAME") or item.get("ID", ""))


def fetch_crm_entities_page(account, entity_type: str, filter_params: dict, start: int = 0) -> dict:
    if entity_type not in SUPPORTED_ENTITY_TYPES:
        raise ValueError(f"Unsupported entity type: {entity_type}")

    request = BitrixAPIRequest(
        bitrix_token=account,
        api_method=CRM_LIST_METHODS[entity_type],
        params={
            "filter": filter_params or {},
            "select": _CRM_TITLE_SELECT[entity_type],
            "start": start,
        },
    )
    api_response = request.response
    items = api_response.result if isinstance(api_response.result, list) else []
    total = int(api_response.total) if api_response.total is not None else len(items)
    next_start = api_response.next

    return {
        "items": items,
        "total": total,
        "next": int(next_start) if next_start is not None else None,
    }


def fetch_crm_entity_ids(account, entity_type: str, filter_params: dict) -> list[int]:
    all_ids = []
    start = 0

    while True:
        page = fetch_crm_entities_page(account, entity_type, filter_params, start=start)
        for item in page["items"]:
            if isinstance(item, dict):
                raw_id = item.get("ID") or item.get("id")
                if raw_id is not None:
                    try:
                        all_ids.append(int(raw_id))
                    except (TypeError, ValueError):
                        pass

        next_start = page.get("next")
        if next_start is None:
            break
        start = next_start

    return all_ids


def execute_bulk_attach(*, session, account, resume_from: int = 0) -> dict:
    from django.conf import settings
    from importer.models import ImportSession

    bulk_config = (session.summary or {}).get("bulk_attach", {})
    entity_type = str(bulk_config.get("entity_type") or "").strip()
    filter_params = bulk_config.get("filter") or {}
    file_url = str(bulk_config.get("file_url") or "").strip()
    file_id = str(bulk_config.get("file_id") or "").strip()
    field_id = str(bulk_config.get("field_id") or "").strip()
    file_name_override = str(bulk_config.get("file_name") or "").strip()
    crm_entity_type = CRM_FILES_ENTITY_TYPES.get(entity_type)

    if not entity_type or not field_id or not crm_entity_type:
        raise ValueError("Bulk attach config is incomplete (entity_type, field_id are required)")
    if not file_url and not file_id:
        raise ValueError("Bulk attach config is incomplete (file_url or file_id is required)")

    entity_ids = fetch_crm_entity_ids(account, entity_type, filter_params)
    total = len(entity_ids)

    resume_from = max(0, min(resume_from, total))
    is_resume = resume_from > 0

    if is_resume:
        # Resume: update total, restore processed cursor, keep existing success/fail counts
        session.total_rows = total
        session.processed_rows = resume_from
        session.save(update_fields=["total_rows", "processed_rows", "updated_at"])
    else:
        session.total_rows = total
        session.processed_rows = 0
        session.successful_rows = 0
        session.failed_rows = 0
        session.save(update_fields=["total_rows", "processed_rows", "successful_rows", "failed_rows", "updated_at"])

    if total == 0 or resume_from >= total:
        session.status = ImportSession.Status.COMPLETED
        session.save(update_fields=["status", "updated_at"])
        return {
            "total": total,
            "successful": int(session.successful_rows or 0),
            "failed": int(session.failed_rows or 0),
            "results": [],
        }

    if file_id:
        upload_dir = os.path.join(settings.MEDIA_ROOT, "bulk-attach-uploads", file_id)
        try:
            file_entries = os.listdir(upload_dir)
        except OSError as error:
            raise ValueError(f"Загруженный файл не найден: {error}")
        if not file_entries:
            raise ValueError("Загруженный файл не найден (пустая директория)")
        disk_file_name = file_entries[0]
        with open(os.path.join(upload_dir, disk_file_name), "rb") as f:
            content = f.read()
        resolved_file_name = file_name_override or disk_file_name
    else:
        try:
            download_result = download_attachment_source(file_url)
        except Exception as error:
            raise ValueError(f"Не удалось загрузить файл: {error}")
        content = download_result.get("content") or b""
        resolved_file_name = file_name_override or download_result.get("file_name") or "attachment.bin"

    results = []
    # Carry over counts when resuming so totals reflect the full operation
    successful = int(session.successful_rows or 0) if is_resume else 0
    failed = int(session.failed_rows or 0) if is_resume else 0

    for i, entity_id in enumerate(entity_ids[resume_from:]):
        actual_index = resume_from + i

        if session.status == ImportSession.Status.CANCELLED:
            break

        try:
            attach_file_to_crm_entity(
                account,
                entity_type=crm_entity_type,
                record_id=entity_id,
                field_id=field_id,
                file_name=resolved_file_name,
                content=content,
            )
            successful += 1
            results.append({"entity_id": entity_id, "status": "success"})
        except Exception as error:
            failed += 1
            results.append({"entity_id": entity_id, "status": "failed", "error": str(error)})

        if (actual_index + 1) % BULK_ATTACH_PROGRESS_INTERVAL == 0:
            session.processed_rows = actual_index + 1
            session.successful_rows = successful
            session.failed_rows = failed
            session.save(update_fields=["processed_rows", "successful_rows", "failed_rows", "updated_at"])
            session.refresh_from_db(fields=["status"])

    session.processed_rows = resume_from + len(results)
    session.successful_rows = successful
    session.failed_rows = failed
    session.save(update_fields=["processed_rows", "successful_rows", "failed_rows", "updated_at"])

    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "results": results,
    }
