# backends/python/ — Django backend (основной)

Django-приложение для импорта Excel/CSV в Bitrix24. Корень Django-проекта — `api/`.

## Структура `api/`

| Файл/папка | Назначение |
|---|---|
| `settings.py` | Django settings (БД, Celery, media, приложения) |
| `config.py` | Конфигурация из env-переменных |
| `urls.py` | Корневой роутинг — подключает `main.urls` и `importer.urls` |
| `app_celery.py` | Инициализация Celery (брокер RabbitMQ) |
| `otel.py` | OpenTelemetry-телеметрия |
| `manage.py`, `wsgi.py`, `asgi.py` | Стандартные точки входа Django |
| `requirements.txt` | Зависимости (django, celery, b24pysdk, openpyxl и др.) |
| `Dockerfile` | Образ контейнера `api-python-worker` |
| `main/` | OAuth-установка приложения, аккаунты Bitrix24 → см. README внутри |
| `importer/` | Ядро импорта → см. README внутри |
| `tests/` | Все backend-тесты → см. README внутри |
| `media/` | Загруженные файлы: `import-sessions/`, `bulk-attach-uploads/` |
| `scripts/` | Вспомогательные скрипты контейнера |

## Тесты

```bash
docker exec api-python-worker python manage.py test                       # все
docker exec api-python-worker python manage.py test api.tests.test_import_report_metadata  # один модуль
```

Известная особенность: в выводе тестов всегда есть pre-existing ошибка `api.main.utils.decorators — RuntimeError: Model class api.main.models.Bitrix24Account doesn't declare an explicit app_label`. Она не связана с кодом импорта.
