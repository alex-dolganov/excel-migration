from celery import shared_task

from .services.background_jobs import (
    execute_import_session_retry_background,
    execute_import_session_run_background,
)


@shared_task(name="importer.run_import_session")
def run_import_session_task(session_id: str, account_id: str):
    return execute_import_session_run_background(session_id=session_id, account_id=account_id)


@shared_task(name="importer.retry_import_session")
def retry_import_session_task(session_id: str, account_id: str):
    return execute_import_session_retry_background(session_id=session_id, account_id=account_id)

