# importer/ — ядро импорта

Django-приложение со всей логикой импорта Excel/CSV в Bitrix24.

## Файлы

### `models.py` (161 строка)
- `EntityType` — TextChoices всех типов сущностей: `lead`, `contact`, `company`, `deal`, `task`, `task_comment`, `task_checklist_item`, `task_attachment`, `crm_files_*`, `crm_activity`, `crm_note`, `user`, `department`, `smart_process` + связки `linked_company_contact`, `linked_company_deal`, `linked_contact_deal`, `linked_contact_company`, `linked_deal_contact`, `linked_deal_company`.
- `ImportSession` — главная модель, state machine: `pending → running → completed/failed`. Хранит файл, маппинг, настройки дедупа, результаты по строкам.
- `ImportTemplate` — сохранённые шаблоны маппинга (advanced-режим).
- `ImportAliasRule` — правила алиасов колонок для автомаппинга.
- `ImporterUserRole` — роли пользователей (см. `services/permissions.py`).

### `tasks.py` (51 строка) — Celery-задачи
| Задача | Что делает |
|---|---|
| `run_import_session_task` | Реальный импорт (принимает `per_row_decisions`) |
| `dry_run_import_session_task` | Тестовый прогон без записи в Bitrix24 |
| `retry_import_session_task` | Повтор только упавших строк |
| `run_bulk_attach_session_task` | Массовое прикрепление файлов (S17) |
| `resume_bulk_attach_session_task` | Возобновление bulk-attach с позиции `resume_from` |
| `cleanup_stuck_sessions_task` | Очистка зависших сессий |

При недоступности RabbitMQ/Celery всё выполняется синхронно.

### `views.py` (~4150 строк) — API endpoints
Константы: `MAX_IMPORT_ROWS=100_000` (env `IMPORT_ROW_LIMIT`), `SAMPLE_PREVIEW_ROW_LIMIT=30`.

`POST .../run` перед постановкой в очередь синхронно выполняет **preflight** (`load_session_preflight_context`), который ходит в Bitrix24 (в т.ч. поиск дублей). Таймаут портала здесь перехватывается как `BitrixRequestTimeout` и возвращается локализованным сообщением со статусом **503** (retryable), а не голым 500. Прочие исключения всплывают в `@log_errors` (500 + тикет).

### Троттлинг запросов к Bitrix24 (`services/import_execution.py`)
Чтобы не упираться в лимиты REST API, между обращениями вставлены паузы (см. `_sleep_if_configured`):
- `BITRIX_ROW_DELAY` (env, по умолчанию `0.1` сек) — пауза между строками;
- `BITRIX_BATCH_DELAY` (env, по умолчанию `1.0` сек) — пауза между батчами.

Установить `0`, чтобы отключить паузы (например, в тестах).

### `urls.py` — карта endpoint'ов (все с префиксом `/api/`)

**Сессии импорта** (`import-sessions`):
- `POST/GET import-sessions` — создать/список
- `GET import-sessions/<id>` — детали (статус, прогресс, результаты)
- `POST .../upload` — загрузка файла
- `GET .../preview` — превью распарсенных строк
- `POST .../mapping` — сохранить маппинг колонок
- `POST .../apply-template` — применить шаблон
- `POST .../validate` — валидация
- `POST .../dry-run` — тестовый прогон
- `POST .../run` — реальный импорт
- `POST .../cancel`, `POST .../retry-failed`
- `GET .../report.csv` — CSV-отчёт по строкам

**Справочники**: `import-fields` (поля сущности), `import-smart-processes`, `import-departments`, `crm-entity-fields`, `crm-file-fields`, `crm-filter-preview`, `import-example-template.xlsx`.

**Настройки**: `import-templates`, `import-alias-rules`, `import-permissions/me`, `import-roles`.

**Bulk attach (S17)**: `bulk-attach-upload`, `bulk-attach-sessions` (create), `.../run`, `.../resume`.

### `services/` — бизнес-логика
См. `services/README.md`.

### `migrations/`
Django-миграции моделей импортера.
