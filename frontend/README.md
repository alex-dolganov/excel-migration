# frontend/ — Nuxt 3 приложение

UI импортёра Bitrix24 (7-шаговый мастер). Запускается внутри Bitrix24 как локальное приложение.

## Структура

| Папка | Назначение | README |
|---|---|---|
| `app/components/` | ImporterWorkbench (мастер), BulkAttachWizard | есть |
| `app/utils/` | `importer-ui.js` — вся UI-бизнес-логика | есть |
| `app/stores/` | Pinia: `api.ts` — все вызовы backend | есть |
| `app/composables/` | `useAppInit`, `useBackend`, `useTelemetry` | есть |
| `app/pages/` | Точки входа: index, install, handler/*, slider/* | есть |
| `app/layouts/` | `default`, `placement`, `slider`, `uf-placement` | — |
| `app/middleware/` | Глобальный роутинг page-or-slider | — |
| `app/plugins/` | `telemetry.client.ts` | — |
| `i18n/locales/` | 19 JSON-локалей (ru, en, br, de, ...) | есть |
| `server/middleware/` | `api-proxy.ts` — прокси `/api/*` на python-backend | — |
| `shared/types/` | `base.d.ts` — общие типы | — |
| `tests/` | Unit-тесты (`node --test`) | есть |
| `public/` | Статика |

## Команды

```bash
node --test tests/*.test.mjs                      # все unit-тесты (из папки frontend/)
docker-compose build frontend && docker-compose up -d frontend   # деплой (production build, без hot-reload)
```

## Ключевые правила

- Названия полей Bitrix24 в UI — только через `formatImporterFieldLabel(fieldId)` из `app/utils/importer-ui.js`. Сырые ID (`TITLE`, `PHONE`) пользователю не показывать.
- При изменении меток полей в `importer-ui.js` — обновить ожидания в `tests/importer-ui.test.mjs`.
