import logging
import os
from datetime import timedelta

from django.utils import timezone

from main.models import Bitrix24Account

from importer.models import ImportSession
from importer.services.error_messages import safe_format_import_error, set_import_error_language

STUCK_SESSION_TIMEOUT_MINUTES = int(os.getenv("IMPORT_STUCK_TIMEOUT_MINUTES", "40"))


def is_import_queue_enabled() -> bool:
    enabled = str(os.getenv("ENABLE_RABBITMQ", "0")).strip().lower()
    broker_url = str(
        os.getenv(
            "CELERY_BROKER_URL",
            os.getenv("RABBITMQ_DSN", ""),
        )
    ).strip()
    return enabled in {"1", "true", "yes", "on"} and bool(broker_url)


def _update_session_job_state(
    session: ImportSession,
    *,
    mode: str,
    state: str,
    task_id: str = "",
    error: str = "",
):
    summary = session.summary if isinstance(session.summary, dict) else {}
    previous_job = summary.get("job") if isinstance(summary.get("job"), dict) else {}
    summary = {
        **summary,
        "job": {
            "mode": str(mode or "").strip(),
            "state": str(state or "").strip(),
            "task_id": str(task_id or previous_job.get("task_id") or "").strip(),
            "error": str(error or "").strip(),
        },
    }
    session.summary = summary


def _send_import_completion_notify(session: ImportSession, account, *, result: dict) -> None:
    try:
        from b24pysdk.bitrix_api.requests import BitrixAPIRequest

        filename = str(session.original_filename or "файл").strip()
        created = int(result.get("created_rows") or 0)
        updated = int(result.get("updated_rows") or 0)
        failed = int(result.get("failed_rows") or 0)
        cancelled = int(result.get("cancelled_rows") or 0)
        is_cancelled = bool(result.get("cancelled"))

        if is_cancelled:
            summary_line = f"Остановлен. Создано: {created}, обновлено: {updated}, не обработано: {cancelled}."
        elif failed > 0:
            summary_line = f"Завершён с ошибками. Создано: {created}, обновлено: {updated}, ошибок: {failed}."
        else:
            summary_line = f"Успешно завершён. Создано: {created}, обновлено: {updated}."

        message = f'Импорт "{filename}" — {summary_line}'
        user_id = int(session.created_by_b24_user_id or 0)
        if not user_id:
            return

        BitrixAPIRequest(
            bitrix_token=account,
            api_method="im.notify.system.add",
            params={"USER_ID": user_id, "MESSAGE": message},
        )
    except Exception as exc:
        logging.warning("Failed to send import completion notify: %s", exc)


def enqueue_import_session_run(session: ImportSession, account, *, per_row_decisions: dict | None = None) -> str:
    from importer.tasks import run_import_session_task

    task = run_import_session_task.delay(
        str(session.id),
        str(getattr(account, "id", "")),
        per_row_decisions,
    )
    session.status = ImportSession.Status.RUNNING
    session.last_error = ""
    _update_session_job_state(session, mode="run", state="queued", task_id=str(getattr(task, "id", "")))
    session.save(update_fields=["status", "summary", "last_error", "updated_at"])
    return str(getattr(task, "id", ""))


def enqueue_import_session_dry_run(session: ImportSession, account, *, mode: str = "preimport_scan") -> str:
    from importer.tasks import dry_run_import_session_task

    task = dry_run_import_session_task.delay(str(session.id), str(getattr(account, "id", "")))
    session.status = ImportSession.Status.RUNNING
    session.last_error = ""
    _update_session_job_state(session, mode=str(mode or "preimport_scan").strip(), state="queued", task_id=str(getattr(task, "id", "")))
    session.save(update_fields=["status", "summary", "last_error", "updated_at"])
    return str(getattr(task, "id", ""))


def enqueue_import_session_retry(session: ImportSession, account) -> str:
    from importer.tasks import retry_import_session_task

    task = retry_import_session_task.delay(str(session.id), str(getattr(account, "id", "")))
    session.status = ImportSession.Status.RUNNING
    session.last_error = ""
    _update_session_job_state(session, mode="retry", state="queued", task_id=str(getattr(task, "id", "")))
    session.save(update_fields=["status", "summary", "last_error", "updated_at"])
    return str(getattr(task, "id", ""))


def enqueue_bulk_attach_session_run(session: ImportSession, account) -> str:
    from importer.tasks import run_bulk_attach_session_task

    task = run_bulk_attach_session_task.delay(str(session.id), str(getattr(account, "id", "")))
    session.status = ImportSession.Status.RUNNING
    session.last_error = ""
    session.save(update_fields=["status", "last_error", "updated_at"])
    return str(getattr(task, "id", ""))


def enqueue_bulk_attach_session_resume(session: ImportSession, account, *, resume_from: int = 0) -> str:
    from importer.tasks import resume_bulk_attach_session_task

    task = resume_bulk_attach_session_task.delay(
        str(session.id),
        str(getattr(account, "id", "")),
        resume_from,
    )
    session.status = ImportSession.Status.RUNNING
    session.last_error = ""
    session.save(update_fields=["status", "last_error", "updated_at"])
    return str(getattr(task, "id", ""))


def execute_bulk_attach_background(*, session_id: str, account_id: str):
    session, account = _load_background_context(session_id, account_id)
    if session.status == ImportSession.Status.CANCELLED:
        return {"session_id": str(session.id), "status": session.status}

    bulk_config = (session.summary or {}).get("bulk_attach", {})
    is_task_bulk_attach = str(bulk_config.get("mode") or "").strip() == "task"
    if is_task_bulk_attach:
        from importer.services.task_bulk_attach import execute_task_bulk_attach
    else:
        from importer.services.bulk_attach import execute_bulk_attach

    try:
        result = execute_task_bulk_attach(session=session, account=account) if is_task_bulk_attach else execute_bulk_attach(session=session, account=account)
    except Exception as error:
        error_message = safe_format_import_error(error)
        session.refresh_from_db()
        session.status = ImportSession.Status.FAILED
        session.last_error = error_message
        session.save(update_fields=["status", "last_error", "updated_at"])
        raise

    session.refresh_from_db()
    if session.status != ImportSession.Status.CANCELLED:
        session.status = ImportSession.Status.COMPLETED
        session.save(update_fields=["status", "updated_at"])

    try:
        bulk_config = (session.summary or {}).get("bulk_attach", {})
        entity_type = str(bulk_config.get("entity_type") or "").strip()
        file_name = str(bulk_config.get("file_name") or bulk_config.get("file_id") or "файл").strip()
        total = int(result.get("total") or 0)
        successful = int(result.get("successful") or 0)
        failed = int(result.get("failed") or 0)
        message = (
            f'Массовое добавление файлов ({entity_type}) — {file_name}. '
            f'Обработано: {total}, успешно: {successful}, ошибок: {failed}.'
        )
        user_id = int(session.created_by_b24_user_id or 0)
        if user_id:
            from b24pysdk.bitrix_api.requests import BitrixAPIRequest
            BitrixAPIRequest(
                bitrix_token=account,
                api_method="im.notify.system.add",
                params={"USER_ID": user_id, "MESSAGE": message},
            ).result
    except Exception as exc:
        logging.warning("Failed to send bulk attach completion notify: %s", exc)

    return result


def execute_bulk_attach_resume_background(*, session_id: str, account_id: str, resume_from: int = 0):
    session, account = _load_background_context(session_id, account_id)
    if session.status == ImportSession.Status.CANCELLED:
        return {"session_id": str(session.id), "status": session.status}

    bulk_config = (session.summary or {}).get("bulk_attach", {})
    is_task_bulk_attach = str(bulk_config.get("mode") or "").strip() == "task"

    try:
        if is_task_bulk_attach:
            from importer.services.task_bulk_attach import execute_task_bulk_attach
            result = execute_task_bulk_attach(session=session, account=account, resume_from=resume_from)
        else:
            from importer.services.bulk_attach import execute_bulk_attach
            result = execute_bulk_attach(session=session, account=account, resume_from=resume_from)
    except Exception as error:
        error_message = safe_format_import_error(error)
        session.refresh_from_db()
        session.status = ImportSession.Status.FAILED
        session.last_error = error_message
        session.save(update_fields=["status", "last_error", "updated_at"])
        raise

    session.refresh_from_db()
    if session.status != ImportSession.Status.CANCELLED:
        session.status = ImportSession.Status.COMPLETED
        session.save(update_fields=["status", "updated_at"])

    try:
        bulk_config = (session.summary or {}).get("bulk_attach", {})
        entity_type = str(bulk_config.get("entity_type") or "").strip()
        file_name = str(bulk_config.get("file_name") or bulk_config.get("file_id") or "файл").strip()
        total = int(result.get("total") or 0)
        successful = int(result.get("successful") or 0)
        failed = int(result.get("failed") or 0)
        message = (
            f'Массовое добавление файлов ({entity_type}) — {file_name}. '
            f'Обработано: {total}, успешно: {successful}, ошибок: {failed}.'
        )
        user_id = int(session.created_by_b24_user_id or 0)
        if user_id:
            from b24pysdk.bitrix_api.requests import BitrixAPIRequest
            BitrixAPIRequest(
                bitrix_token=account,
                api_method="im.notify.system.add",
                params={"USER_ID": user_id, "MESSAGE": message},
            ).result
    except Exception as exc:
        logging.warning("Failed to send bulk attach resume completion notify: %s", exc)

    return result


def _load_background_context(session_id: str, account_id: str) -> tuple[ImportSession, Bitrix24Account]:
    session = ImportSession.objects.get(id=session_id)
    account = Bitrix24Account.objects.get(pk=account_id)
    import_settings = session.import_settings if isinstance(session.import_settings, dict) else {}
    set_import_error_language(import_settings.get("language"))
    return session, account


def execute_import_session_run_background(*, session_id: str, account_id: str, per_row_decisions: dict | None = None):
    from importer.views import execute_import_session_run_now

    session, account = _load_background_context(session_id, account_id)
    if session.status == ImportSession.Status.CANCELLED:
        _update_session_job_state(session, mode="run", state="cancelled")
        session.save(update_fields=["summary", "updated_at"])
        return {"session_id": str(session.id), "status": session.status}

    _update_session_job_state(session, mode="run", state="running")
    session.save(update_fields=["summary", "updated_at"])
    try:
        result = execute_import_session_run_now(
            session=session,
            account=account,
            per_row_decisions=per_row_decisions,
        )
    except Exception as error:
        error_message = safe_format_import_error(error)
        session.refresh_from_db()
        session.status = ImportSession.Status.FAILED
        session.last_error = error_message
        _update_session_job_state(session, mode="run", state="failed", error=error_message)
        session.save(update_fields=["status", "last_error", "summary", "updated_at"])
        raise
    session.refresh_from_db()
    _update_session_job_state(
        session,
        mode="run",
        state="cancelled" if session.status == ImportSession.Status.CANCELLED else "completed",
    )
    session.save(update_fields=["summary", "updated_at"])
    _send_import_completion_notify(session, account, result=result)
    return result


def execute_import_session_dry_run_background(*, session_id: str, account_id: str):
    from importer.views import execute_import_session_dry_run_now

    session, account = _load_background_context(session_id, account_id)
    summary = session.summary if isinstance(session.summary, dict) else {}
    job = summary.get("job") if isinstance(summary.get("job"), dict) else {}
    job_mode = str(job.get("mode") or "preimport_scan").strip() or "preimport_scan"
    if session.status == ImportSession.Status.CANCELLED:
        _update_session_job_state(session, mode=job_mode, state="cancelled")
        session.save(update_fields=["summary", "updated_at"])
        return {"session_id": str(session.id), "status": session.status}

    _update_session_job_state(session, mode=job_mode, state="running")
    session.save(update_fields=["summary", "updated_at"])
    try:
        result = execute_import_session_dry_run_now(session=session, account=account, mode=job_mode)
    except Exception as error:
        error_message = safe_format_import_error(error)
        session.refresh_from_db()
        session.status = ImportSession.Status.FAILED
        session.last_error = error_message
        _update_session_job_state(session, mode=job_mode, state="failed", error=error_message)
        session.save(update_fields=["status", "last_error", "summary", "updated_at"])
        raise
    session.refresh_from_db()
    _update_session_job_state(
        session,
        mode=job_mode,
        state="cancelled" if session.status == ImportSession.Status.CANCELLED else "completed",
    )
    session.save(update_fields=["summary", "updated_at"])
    return result


def execute_import_session_retry_background(*, session_id: str, account_id: str):
    from importer.views import execute_import_session_retry_now

    session, account = _load_background_context(session_id, account_id)
    if session.status == ImportSession.Status.CANCELLED:
        _update_session_job_state(session, mode="retry", state="cancelled")
        session.save(update_fields=["summary", "updated_at"])
        return {"session_id": str(session.id), "status": session.status}

    _update_session_job_state(session, mode="retry", state="running")
    session.save(update_fields=["summary", "updated_at"])
    try:
        result = execute_import_session_retry_now(session=session, account=account)
    except Exception as error:
        error_message = safe_format_import_error(error)
        session.refresh_from_db()
        session.status = ImportSession.Status.FAILED
        session.last_error = error_message
        _update_session_job_state(session, mode="retry", state="failed", error=error_message)
        session.save(update_fields=["status", "last_error", "summary", "updated_at"])
        raise
    session.refresh_from_db()
    _update_session_job_state(
        session,
        mode="retry",
        state="cancelled" if session.status == ImportSession.Status.CANCELLED else "completed",
    )
    session.save(update_fields=["summary", "updated_at"])
    retry_result = result.get("retry_result") if isinstance(result, dict) else {}
    _send_import_completion_notify(session, account, result=retry_result if isinstance(retry_result, dict) else result)
    return result


def cleanup_stuck_import_sessions() -> dict:
    cutoff = timezone.now() - timedelta(minutes=STUCK_SESSION_TIMEOUT_MINUTES)
    stuck_sessions = ImportSession.objects.filter(
        status=ImportSession.Status.RUNNING,
        updated_at__lt=cutoff,
    )
    fixed = 0
    for session in stuck_sessions:
        try:
            session.status = ImportSession.Status.FAILED
            session.last_error = (
                f"Импорт завершился с ошибкой: воркер не отвечал более {STUCK_SESSION_TIMEOUT_MINUTES} минут. "
                "Попробуйте повторить неуспешные строки."
            )
            _update_session_job_state(session, mode="run", state="failed", error=session.last_error)
            session.save(update_fields=["status", "last_error", "summary", "updated_at"])
            fixed += 1
            logging.warning("Marked stuck import session %s as failed", session.id)
        except Exception as exc:
            logging.error("Failed to cleanup stuck session %s: %s", session.id, exc)
    return {"fixed": fixed}
