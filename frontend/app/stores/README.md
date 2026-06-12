# app/stores/ — Pinia-сторы

| Стор | Строк | Назначение |
|---|---|---|
| `api.ts` | ~625 | `useApiStore` — **все вызовы backend** (сессии импорта, upload, mapping, dry-run, run, отчёты, справочники, bulk-attach). Ходит через серверный прокси `/api/*` (`server/middleware/api-proxy.ts`) |
| `appSettings.ts` | 88 | Настройки приложения |
| `userSettings.ts` | 70 | Пользовательские настройки |
| `user.ts` | 64 | Текущий пользователь Bitrix24 |
| `page.ts` | 17 | Состояние страницы (заголовок и т.п.) |

Правило: новые вызовы backend добавлять в `api.ts`, не делать fetch напрямую из компонентов.
