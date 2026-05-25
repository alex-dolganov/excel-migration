# Import Production Checklist

## Before Code Review

- [ ] Описание проекта обновлено: что импортирует сервис, какие сущности поддерживает, какие ограничения по размеру/строкам есть.
- [ ] Локально проверены `preview`, `validate`, `run`, `retry`, `cancel`.
- [ ] Проверен импорт на одном тестовом портале.
- [ ] Для крупных файлов проверен хотя бы один сценарий `CSV`.
- [ ] Подготовлены и обновлены:
  - [ ] `.env.example`
  - [ ] `docker-compose.yml`
  - [ ] `infrastructure/database/init-mysql.sql`
  - [ ] release templates из `docs/release/`

## Code Review And Security

- [ ] Создана задача на Максима.
- [ ] В задаче есть ссылка на репозиторий и ветку/коммит.
- [ ] Если нужно, `horokey` добавлен в доступы GitHub.
- [ ] После сборки образ запушен в `registry.i.bitrix24.ru`.
- [ ] Harbor scan не содержит `Critical`.
- [ ] Harbor scan не содержит `High`.

## Infra Handoff

- [ ] Создан новый release tag образа.
- [ ] Новый tag указан в задаче облачным администраторам.
- [ ] Указан целевой домен.
- [ ] Приложены:
  - [ ] `.env` example
  - [ ] `docker-compose` example/reference
  - [ ] SQL/init notes
  - [ ] требования к внешним `MySQL`, `RabbitMQ`, `Nginx`
  - [ ] OTLP/OpenTelemetry переменные

## Production Contract

- [ ] Прод использует внешний `MySQL`.
- [ ] Прод использует внешний `RabbitMQ`.
- [ ] Публикация идет только через Harbor image tag.
- [ ] Для изменений образа используется новый tag, а не перезапись старого.
- [ ] Debug-поведение ограничено и включается осознанно.
- [ ] После публикации учтено, что логи надо запрашивать у администраторов отдельно.
