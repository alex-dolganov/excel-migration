import os

from celery import Celery


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")


broker_url = os.getenv(
    "CELERY_BROKER_URL",
    os.getenv("RABBITMQ_DSN", "amqp://queue_user:queue_password@rabbitmq:5672/%2f"),
)

celery_app = Celery("excel_migration_app", broker=broker_url)
celery_app.conf.task_acks_late = True
celery_app.conf.worker_prefetch_multiplier = int(os.getenv("RABBITMQ_PREFETCH", "5"))
celery_app.conf.task_default_queue = "importer.import-jobs"
celery_app.autodiscover_tasks(["importer"])
