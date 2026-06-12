# Внутренняя библиотека проекта

Индекс описаний всех разделов. В каждой папке лежит `README.md` с детальным описанием её содержимого — читайте его вместо сканирования файлов.

## Что это за проект

**Bitrix24 Excel Import** — приложение для импорта CRM-данных (лиды, контакты, компании, сделки, задачи, смарт-процессы) из Excel/CSV в Bitrix24 через 7-шаговый мастер. Стек: Nuxt 3 (frontend) + Django/Celery (backend) + Docker Compose.

## Карта разделов

| Раздел | Описание | README |
|---|---|---|
| `backends/` | Три backend-варианта; **рабочий — python** | [backends/README.md](backends/README.md) |
| `backends/python/` | Django-приложение (основной backend) | [backends/python/README.md](backends/python/README.md) |
| `backends/python/api/importer/` | Ядро импорта: модели, 27 endpoint'ов, Celery-задачи | [importer/README.md](backends/python/api/importer/README.md) |
| `backends/python/api/importer/services/` | Бизнес-логика импорта (17 сервисов, ~14k строк) | [services/README.md](backends/python/api/importer/services/README.md) |
| `backends/python/api/main/` | OAuth/установка приложения, аккаунты Bitrix24 | [main/README.md](backends/python/api/main/README.md) |
| `backends/python/api/tests/` | 27 тестовых модулей backend | [tests/README.md](backends/python/api/tests/README.md) |
| `frontend/` | Nuxt 3 приложение | [frontend/README.md](frontend/README.md) |
| `frontend/app/components/` | ImporterWorkbench (мастер), BulkAttachWizard | [components/README.md](frontend/app/components/README.md) |
| `frontend/app/utils/` | importer-ui.js — вся UI-логика импортера | [utils/README.md](frontend/app/utils/README.md) |
| `frontend/app/stores/` | Pinia-сторы (api.ts — все вызовы backend) | [stores/README.md](frontend/app/stores/README.md) |
| `frontend/tests/` | Unit-тесты UI-логики (node --test) | [tests/README.md](frontend/tests/README.md) |
| `infrastructure/` | Nginx-конфиги, init-скрипты БД | [infrastructure/README.md](infrastructure/README.md) |
| `docs/` | Релизные чек-листы и шаблоны | [docs/README.md](docs/README.md) |
| `instructions/` | База знаний по Bitrix24 API и стеку | [instructions/README.md](instructions/README.md) |
| `scripts/` | Скрипты dev-окружения и security-сканов | [scripts/README.md](scripts/README.md) |

## Быстрые факты (чтобы не искать)

- **Мастер импорта, 7 шагов**: Source → Structure → Field Mapping → Dedup → Validation → Dry Run → Import Results.
- **Лимиты**: `MAX_IMPORT_ROWS=100_000` (настраивается через `IMPORT_ROW_LIMIT`), `SAMPLE_PREVIEW_ROW_LIMIT=30` — оба в `importer/views.py`.
- **Очередь**: RabbitMQ + Celery; при недоступности — синхронное выполнение.
- **Tasks API**: `b24pysdk` не имеет tasks scope — все `tasks.task.*` только через `BitrixAPIRequest`.
- **Деплой backend**: `docker cp <файл> api-python-worker:/var/www/api/...` (без rebuild).
- **Деплой frontend**: `docker-compose build frontend && docker-compose up -d frontend`.
- **Тесты backend**: `docker exec api-python-worker python manage.py test`.
- **Тесты frontend**: `node --test tests/*.test.mjs` (из папки `frontend/`).
- **Локализация UI**: 19 локалей в `frontend/i18n/locales/`; названия полей переводятся через `formatImporterFieldLabel()` из `importer-ui.js` — сырые ID полей (TITLE, PHONE) в UI не показывать.
