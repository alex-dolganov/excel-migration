# backends/

Три варианта backend'а из стартер-кита Bitrix24. **Рабочий backend проекта — `python/`**, остальные оставлены как заготовки стартер-кита и в импорте не участвуют.

| Папка | Стек | Статус |
|---|---|---|
| `python/` | Django + Celery + b24pysdk | **Основной** — вся логика импорта здесь |
| `node/` | Express, один `server.js` (~CRUD к Postgres/MySQL, JWT-проверка токена Bitrix24) | Заготовка стартер-кита |
| `php/` | Symfony + bitrix24-php-sdk (composer, migrations, phpstan/rector) | Заготовка стартер-кита |

Контейнеры python-backend'а: `api-python-worker` (Django + Celery worker). Рабочая директория внутри контейнера: `/var/www/api`.

Деплой изменений python-кода без rebuild:
```bash
docker cp backends/python/api/<путь>.py api-python-worker:/var/www/api/<путь>.py
```
