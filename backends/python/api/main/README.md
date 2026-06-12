# main/ — установка приложения и аккаунты Bitrix24

Django-приложение, отвечающее за OAuth-жизненный цикл приложения в Bitrix24 (не за импорт).

## Файлы

- `models.py`:
  - `Bitrix24Account` (наследует `AbstractBitrixToken` из b24pysdk) — портал, токены доступа/обновления. Используется во всех вызовах Bitrix24 API.
  - `ApplicationInstallation` — факт установки приложения на портал.
- `views.py` — обработчики установки/событий приложения (install, OAuth-handshake).
- `urls.py` — роуты установки.
- `admin.py` — регистрация моделей в Django admin.
- `utils/` — вспомогательные утилиты, в т.ч. `decorators.py` (даёт известную pre-existing ошибку `app_label` в выводе тестов — игнорировать).
