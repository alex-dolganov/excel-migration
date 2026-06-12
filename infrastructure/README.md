# infrastructure/

## nginx/
- `python-app.conf` — рабочий nginx-конфиг: роутинг фронта и проксирование `/api/*` на python-backend, лимиты размера загрузки (`client_max_body_size`).
- `python-app.conf.template` + `render-python-app-conf.mjs` — шаблон и генератор конфига из env-переменных. **Правки делать в шаблоне**, конфиг — генерируемый.
- Контракт конфига проверяется тестом `frontend/tests/importer-nginx-contract.test.mjs`.

## database/
Init-скрипты, выполняемые при первом старте контейнера БД:
- `init.sql` — PostgreSQL
- `init-mysql.sql` — MySQL (node-backend)
- `init-python-mysql.sql` — MySQL для python-backend
