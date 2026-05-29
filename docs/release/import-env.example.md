# Import Environment Contract

## Required For Production

```env
BUILD_TARGET=production

# Database (external MySQL only in production)
DB_TYPE=mysql
DB_HOST=<external-mysql-host>
DB_PORT=3306
DB_NAME=<db-name>
DB_USER=<db-user>
DB_PASSWORD=<db-password>

# RabbitMQ (external in production)
ENABLE_RABBITMQ=1
RABBITMQ_USER=<rabbit-user>
RABBITMQ_PASSWORD=<rabbit-password>
RABBITMQ_PREFETCH=5
RABBITMQ_DSN=amqp://<rabbit-user>:<rabbit-password>@<rabbit-host>:5672/%2f

# Auth
JWT_SECRET=<your-jwt-secret>
JWT_ALGORITHM=HS256
CLIENT_ID=<bitrix24-app-client-id>
CLIENT_SECRET=<bitrix24-app-client-secret>
VIRTUAL_HOST=https://<your-domain>

# Runtime tuning
GUNICORN_WORKERS=2
GUNICORN_TIMEOUT=600
GUNICORN_GRACEFUL_TIMEOUT=60
GUNICORN_KEEPALIVE=5
CELERY_CONCURRENCY=2
BITRIX_ROW_DELAY=0
BITRIX_BATCH_DELAY=0.5
IMPORT_PROGRESS_SAVE_INTERVAL=100
IMPORT_MAX_FILE_SIZE_BYTES=52428800

# Nginx alignment (optional overrides)
NGINX_CLIENT_MAX_BODY_SIZE=
NGINX_PROXY_SEND_TIMEOUT=600s
NGINX_PROXY_READ_TIMEOUT=600s

# OpenTelemetry — traces + structured logs → Grafana
OTEL_EXPORTER_OTLP_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=<otlp-collector-endpoint>
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer <token>
OTEL_SERVICE_NAME=excel-migration-api
OTEL_SERVICE_VERSION=<release-tag>
OTEL_ENVIRONMENT=production

# Per-portal debug (comma-separated member_ids, empty = disabled)
DEBUG_PORTALS=

# Error tickets via internal proxy (disabled by default)
ERROR_TICKETS_ENABLED=false
ERROR_TICKETS_ENDPOINT=https://mptools.mplace.bx/api/error-ticket
```

## Notes

- В проде не поднимаем локальные контейнеры `MySQL` и `RabbitMQ`, только подключаемся к внешним сервисам.
- `BITRIX_ROW_DELAY=0` нужен для быстрого импорта; трогаем только если реально видим rate limit.
- `IMPORT_PROGRESS_SAVE_INTERVAL=100` уменьшает лишние записи прогресса в БД без потери итогового статуса.
- `OTEL_SERVICE_VERSION` удобно синхронизировать с Harbor tag — так в Grafana видно какая версия сервиса отправила трейс/лог.
- `DEBUG_PORTALS` — безопасный способ включить подробное логирование для конкретного портала без global debug.
- `ERROR_TICKETS_ENABLED=true` включает автоматическую отправку тикетов с trace_id при ошибках. Endpoint не светится в клиенте — только в серверном env.
- Логи недоступны напрямую в облаке — все диагностика идёт через OTel → Grafana + тикеты.
