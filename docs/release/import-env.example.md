# Import Environment Contract

## Required For Production

```env
BUILD_TARGET=production
DB_TYPE=mysql
DB_HOST=<external-mysql-host>
DB_PORT=3306
DB_NAME=<db-name>
DB_USER=<db-user>
DB_PASSWORD=<db-password>

ENABLE_RABBITMQ=1
RABBITMQ_USER=<rabbit-user>
RABBITMQ_PASSWORD=<rabbit-password>
RABBITMQ_PREFETCH=5
RABBITMQ_DSN=amqp://<rabbit-user>:<rabbit-password>@<rabbit-host>:5672/%2f

GUNICORN_WORKERS=2
GUNICORN_TIMEOUT=600
CELERY_CONCURRENCY=2
BITRIX_ROW_DELAY=0
BITRIX_BATCH_DELAY=0.5
IMPORT_PROGRESS_SAVE_INTERVAL=100

OTEL_EXPORTER_OTLP_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=<otlp-endpoint>
OTEL_EXPORTER_OTLP_HEADERS=<otlp-headers>
OTEL_SERVICE_NAME=excel-migration-api
OTEL_SERVICE_VERSION=<release-tag>
OTEL_ENVIRONMENT=production
```

## Notes

- В проде не поднимаем локальные контейнеры `MySQL` и `RabbitMQ`, только подключаемся к внешним сервисам.
- `BITRIX_ROW_DELAY=0` нужен для быстрого импорта; трогаем только если реально видим rate limit и хотим временно притормозить non-batch path.
- `IMPORT_PROGRESS_SAVE_INTERVAL=100` уменьшает лишние записи прогресса в БД без потери итогового статуса.
- `OTEL_SERVICE_VERSION` удобно синхронизировать с Harbor tag.
