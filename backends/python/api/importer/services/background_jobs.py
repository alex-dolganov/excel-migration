import os

from main.models import Bitrix24Account

from importer.models import ImportSession
from importer.services.error_messages import safe_format_import_error


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


def enqueue_import_session_run(session: ImportSession, account) -> str:
    from importer.tasks import run_import_session_task

    task = run_import_session_task.delay(str(session.id), str(getattr(account, "id", "")))
    session.status = ImportSession.Status.RUNNING
    session.last_error = ""
    _update_session_job_state(session, mode="run", state="queued", task_id=str(getattr(task, "id", "")))
    session.save(update_fields=["status", "summary", "last_error", "updated_at"])
    return str(getattr(task, "id", ""))


def enqueue_import_session_dry_run(session: ImportSession, account) -> str:
    from importer.tasks import dry_run_import_session_task

    task = dry_run_import_session_task.delay(str(session.id), str(getattr(account, "id", "")))
    session.status = ImportSession.Status.RUNNING
    session.last_error = ""
    _update_session_job_state(session, mode="dry_run", state="queued", task_id=str(getattr(task, "id", "")))
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


def _load_background_context(session_id: str, account_id: str) -> tuple[ImportSession, Bitrix24Account]:
    session = ImportSession.objects.get(id=session_id)
    account = Bitrix24Account.objects.get(pk=account_id)
    return session, account


def execute_import_session_run_background(*, session_id: str, account_id: str):
    from importer.views import execute_import_session_run_now

    session, account = _load_background_context(session_id, account_id)
    if session.status == ImportSession.Status.CANCELLED:
        _update_session_job_state(session, mode="run", state="cancelled")
        session.save(update_fields=["summary", "updated_at"])
        return {"session_id": str(session.id), "status": session.status}

    _update_session_job_state(session, mode="run", state="running")
    session.save(update_fields=["summary", "updated_at"])
    try:
        result = execute_import_session_run_now(session=session, account=account)
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
    return result


def execute_import_session_dry_run_background(*, session_id: str, account_id: str):
    from importer.views import execute_import_session_dry_run_now

    session, account = _load_background_context(session_id, account_id)
    if session.status == ImportSession.Status.CANCELLED:
        _update_session_job_state(session, mode="dry_run", state="cancelled")
        session.save(update_fields=["summary", "updated_at"])
        return {"session_id": str(session.id), "status": session.status}

    _update_session_job_state(session, mode="dry_run", state="running")
    session.save(update_fields=["summary", "updated_at"])
    try:
        result = execute_import_session_dry_run_now(session=session, account=account)
    except Exception as error:
        error_message = safe_format_import_error(error)
        session.refresh_from_db()
        session.status = ImportSession.Status.FAILED
        session.last_error = error_message
        _update_session_job_state(session, mode="dry_run", state="failed", error=error_message)
        session.save(update_fields=["status", "last_error", "summary", "updated_at"])
        raise
    session.refresh_from_db()
    _update_session_job_state(session, mode="dry_run", state="completed")
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
    return result
