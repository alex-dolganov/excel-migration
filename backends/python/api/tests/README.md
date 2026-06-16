# tests/ — backend-тесты (Django)

Запуск: `docker exec api-python-worker python manage.py test tests` (НЕ pytest напрямую).
Один модуль: `docker exec api-python-worker python manage.py test tests.<имя_модуля>`.
Рабочая директория контейнера — `/var/www/api`, поэтому путь модуля `tests.*`, а не `api.tests.*`.

## Карта тестов → что покрывают

| Модуль | Покрывает |
|---|---|
| `test_import_sessions_api.py` | CRUD сессий импорта |
| `test_import_file_upload_api.py` | Загрузка файлов (лимиты, кодировки) |
| `test_import_preview_api.py` | Превью строк |
| `test_import_mapping_api.py` / `test_mapping_service.py` | Маппинг колонок (API / сервис) |
| `test_import_validation_api.py` / `test_import_validation_service.py` | Валидация |
| `test_import_dry_run_api.py` | Dry-run |
| `test_import_execution_api.py` / `test_import_execution_service.py` / `test_import_execution_batch.py` | Реальный импорт (API / сервис / batch) |
| `test_import_report_metadata.py` | `build_report_title()` и report-метаданные — **обновлять при изменении `report_metadata.py`** |
| `test_import_preflight_service.py` | Предпроверки |
| `test_import_field_catalog_api.py` | Каталог полей (`import-fields`) |
| `test_import_smart_processes_api.py` | Смарт-процессы |
| `test_import_templates_api.py` / `test_import_example_templates_api.py` | Шаблоны маппинга / XLSX-примеры |
| `test_import_permissions_api.py` | Роли и права |
| `test_bulk_attach_preview_api.py` / `test_bulk_attach_session_api.py` / `test_task_bulk_attach_service.py` | Bulk attach (S17) |
| `test_task_attachments.py` | Вложения задач |
| `test_value_normalization_service.py` | Нормализация значений |
| `test_error_messages.py` | Перевод ошибок API |
| `test_importer_models.py` | Модели импортера |
| `test_main_api.py` | Приложение `main` (установка) |
| `test_python_prod_contract.py` | Контракт production-конфигурации |

Известная pre-existing ошибка в выводе: `RuntimeError: Model class api.main.models.Bitrix24Account doesn't declare an explicit app_label` — не связана с импортом.
