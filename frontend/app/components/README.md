# app/components/

| Компонент | Строк | Назначение |
|---|---|---|
| `ImporterWorkbench.vue` | ~8700 | **Главный компонент** — 7-шаговый мастер импорта: Source (загрузка файла) → Structure (заголовки) → Field Mapping → Dedup Settings → Validation (превью 30 строк) → Dry Run (колонка «Что уйдет в Bitrix24») → Import Results (колонка «Что попало в Bitrix24»). Два режима: Simple (файл + тип + маппинг) и Advanced (шаблоны, дедуп, отчёт по строкам, CSV-экспорт). Вся вычислимая логика вынесена в `app/utils/importer-ui.js` |
| `BulkAttachWizard.vue` | ~970 | S17 — массовое прикрепление файлов к сущностям CRM/задачам, с возобновлением с места остановки |
| `AppLanding.vue` | ~220 | Лендинг/стартовый экран приложения |
| `BackendStatus.vue` | ~65 | Индикатор доступности backend |
| `Logo.vue` | 7 | Логотип |

Правило: не добавлять бизнес-логику в `ImporterWorkbench.vue` — выносить в `importer-ui.js`, где она покрывается unit-тестами.
