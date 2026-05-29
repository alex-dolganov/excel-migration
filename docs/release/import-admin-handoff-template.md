# Cloud Admin Handoff Template

## Данные для задачи

**Проект:**  
`<название проекта>`

**Описание:**  
`<краткое описание сервиса и сценария импорта>`

**Домен:**  
`<required-domain>`

**Docker image tags:**  
- API: `registry.i.bitrix24.ru/<project>/api-python:<tag>`
- Frontend: `registry.i.bitrix24.ru/<project>/frontend:<tag>`

## Файлы для администраторов

1. `.env` example — `docs/release/import-env.example.md`
2. Production compose — `docker-compose.prod.yml` (только api-python, worker, frontend)
3. Nginx config — `infrastructure/nginx/python-app.conf`
4. MySQL init — `infrastructure/database/init-python-mysql.sql` (создать БД и пользователя)
5. Nginx template — `infrastructure/nginx/python-app.conf.template`

## Требования к внешним сервисам

### MySQL
- Версия: MySQL 8.x
- База данных и пользователь создаются по `init-python-mysql.sql`
- Django применяет миграции автоматически при старте (`manage.py migrate`)

### RabbitMQ
- `RABBITMQ_DSN=amqp://<user>:<pass>@<host>:5672/%2f`
- Нужен отдельный воркер-контейнер (`api-python-worker`)

### Nginx (внешний в облаке)
- Проксировать запросы на `api-python:8000`
- `client_max_body_size` — выставить под `IMPORT_MAX_FILE_SIZE_BYTES` (по умолчанию 50m)
- `proxy_read_timeout 600s`, `proxy_send_timeout 600s`
- Пример конфига: `infrastructure/nginx/python-app.conf`

### OpenTelemetry (трейсы + логи → Grafana)
- `OTEL_EXPORTER_OTLP_ENABLED=true`
- `OTEL_EXPORTER_OTLP_ENDPOINT=<collector-endpoint>`
- `OTEL_SERVICE_NAME=excel-migration-api`
- `OTEL_SERVICE_VERSION=<image-tag>` — для привязки трейсов к версии

## Важные замечания для администраторов

- Использовать **новый tag** образа, не переиспользовать старый
- `BUILD_TARGET=production` обязательно — иначе стартует dev-сервер
- В проде **не нужны** контейнеры `database-mysql`, `rabbitmq` из `docker-compose.yml` — только api-python + worker + frontend из `docker-compose.prod.yml`
- Если после выкладки нужна диагностика — логи запрашивать у администраторов; самостоятельно смотреть через Grafana по trace_id

## Описание изменений (заполнить перед отправкой)

- `<что изменилось в этом релизе>`

## Чеклист перед отправкой задачи администраторам

- [ ] Образ собран и запушен в Harbor
- [ ] Harbor vulnerability scan пройден: нет Critical, нет High
- [ ] Новый image tag указан в задаче
- [ ] .env example приложен
- [ ] docker-compose.prod.yml приложен
- [ ] Nginx config приложен
- [ ] MySQL init SQL приложен
