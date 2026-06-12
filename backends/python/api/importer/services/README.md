# importer/services/ — бизнес-логика импорта (~10 000 строк)

| Файл | Строк | Назначение |
|---|---|---|
| `import_execution.py` | 3663 | **Главный сервис.** Основной цикл импорта: построчная обработка, вызовы Bitrix24 API, дедупликация, batch-запросы, linked-сущности (`build_linked_mapping_groups`, `build_linked_record_title`). Для каждой строки вызывает `build_import_result_report_meta()` |
| `b24_fields.py` | 1761 | Определения полей Bitrix24 по типам сущностей, `SMART_PROCESS_ENTITY_TYPE`, `get_linked_import_schema()`. Каталог полей для маппинга |
| `validation.py` | 639 | Валидация строк перед импортом, `normalize_value()` |
| `example_templates.py` | 811 | Генерация примеров XLSX-шаблонов (свой ZIP/XML-писатель без openpyxl) |
| `mapping.py` | 471 | Автомаппинг колонок на поля (fuzzy-match через `SequenceMatcher`), `resolve_field_item_value()` |
| `preflight.py` | 406 | Предпроверки перед запуском импорта |
| `background_jobs.py` | 377 | Запуск задач через Celery с fallback на синхронное выполнение; cleanup зависших сессий |
| `report_metadata.py` | 328 | `build_import_result_report_meta()` → `report_entity`, `report_title`, `report_record_id` для каждой строки отчёта. **Важно**: `build_report_title()` для лидов имеет fallback-цепочку `TITLE → NAME+LAST_NAME → EMAIL → PHONE`; остальные сущности — только `TITLE` |
| `task_attachments.py` | 244 | Прикрепление файлов к задачам (через Disk API) |
| `value_normalization.py` | 209 | Нормализация значений (даты, телефоны, дискретные значения — `build_discrete_value_keys`) |
| `bulk_attach.py` | 198 | Массовое прикрепление файлов к CRM-сущностям (S17) |
| `task_bulk_attach.py` | 196 | Массовое прикрепление файлов к задачам, поддержка resume |
| `user_resolution.py` | 182 | Резолв пользователей Bitrix24 (по email/имени → ID) |
| `error_messages.py` | 244 | Перевод ошибок Bitrix24 API в человекочитаемые сообщения |
| `excel_values.py` | 138 | Парсинг значений Excel (даты-serial, форматы) |
| `task_resolution.py` | 114 | `invoke_with_fallbacks()` — вызов tasks API с fallback'ами. **tasks.task.\* только через `BitrixAPIRequest`** (b24pysdk не имеет tasks scope) |
| `permissions.py` | 73 | Роли: `portal_admin`, `operator`, `viewer`, `none`; `ASSIGNABLE_ROLES` |

## Ключевые правила

- Все вызовы `tasks.task.*` — через `BitrixAPIRequest`, не через SDK.
- При изменении `build_report_title()` — обновить `tests/test_import_report_metadata.py`.
- Деплой без rebuild: `docker cp backends/python/api/importer/services/<файл>.py api-python-worker:/var/www/api/importer/services/<файл>.py`.
