try:
    from app_celery import celery_app
except ModuleNotFoundError:
    from api.app_celery import celery_app


@celery_app.task(name="main.refresh_expiring_tokens")
def refresh_expiring_tokens_task():
    from main.services.token_refresh import refresh_expiring_tokens
    return refresh_expiring_tokens()
