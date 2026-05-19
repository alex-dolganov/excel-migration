try:
    from app_celery import celery_app
except ModuleNotFoundError:
    from api.app_celery import celery_app

from .services.background_jobs import (
    cleanup_stuck_import_sessions,
    execute_import_session_dry_run_background,
    execute_import_session_retry_background,
    execute_import_session_run_background,
)


@celery_app.task(name="importer.run_import_session")
def run_import_session_task(session_id: str, account_id: str):
    return execute_import_session_run_background(session_id=session_id, account_id=account_id)


@celery_app.task(name="importer.dry_run_import_session")
def dry_run_import_session_task(session_id: str, account_id: str):
    return execute_import_session_dry_run_background(session_id=session_id, account_id=account_id)


@celery_app.task(name="importer.retry_import_session")
def retry_import_session_task(session_id: str, account_id: str):
    return execute_import_session_retry_background(session_id=session_id, account_id=account_id)


@celery_app.task(name="importer.cleanup_stuck_sessions")
def cleanup_stuck_sessions_task():
    return cleanup_stuck_import_sessions()
