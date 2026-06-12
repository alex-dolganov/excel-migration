# app/pages/ — точки входа (все client-only, `.client.vue`)

| Страница | Назначение |
|---|---|
| `index.client.vue` | Главная — рендерит мастер импорта (ImporterWorkbench) |
| `install.client.vue` | Страница установки приложения в Bitrix24 |
| `telemetry-test.client.vue` | Тест телеметрии |
| `handler/placement-crm-deal-detail-tab.client.vue` | Placement-вкладка в карточке сделки |
| `handler/uf.demo.client.vue` | Демо пользовательского поля (UF) |
| `handler/background-some-problem.client.vue` | Обработчик фоновых ошибок |
| `slider/app-options.client.vue` | Настройки приложения в слайдере Bitrix24 |

Выбор layout (page или slider) делает глобальный middleware `app/middleware/01.app.page.or.slider.global.ts`. Layouts: `default`, `placement`, `slider`, `uf-placement`.
