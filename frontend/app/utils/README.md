# app/utils/

| Файл | Строк | Назначение |
|---|---|---|
| `importer-ui.js` | ~3350 | **Вся UI-бизнес-логика импортёра** (см. ниже) |
| `downloads.js` | 45 | Скачивание файлов (CSV-отчёты) |
| `index-page-init.js` | 18 | Инициализация главной страницы |
| `chunkArray.ts` | 68 | Разбиение массива на чанки |
| `scrollToTop.ts`, `sleep.ts` | <10 | Мелкие хелперы |

## importer-ui.js — ключевые экспорты

- `formatImporterFieldLabel(fieldId, fieldTitle, t)` — перевод API-ID полей Bitrix24 в человекочитаемые названия через i18n (`importer.field_labels.*`); без переданного `t` использует RU-fallback `IMPORTER_FIELD_LABELS` (`TITLE` → «Название / заголовок», `PHONE` → «Телефон»). **Обязателен для любого показа полей в UI.**
- `IMPORTER_FIELD_LABELS` (~строка 1500) — RU-fallback карта переводов полей.
- `buildFlatDryRunRows()` — строит строки таблицы dry-run; использует `formatImporterFieldLabel()`.
- `buildFlatImportRunRows()` — строит строки таблицы реального импорта; использует `report_title` из backend.
- `dryRunTableColumns` / `importRunTableColumns` — определения колонок таблиц.
- Логика дедуп-меток, linked-метаданных, simple-режима, лимитов загрузки (по этим зонам — отдельные тестовые файлы в `frontend/tests/`).

Тесты: `node --test tests/importer-ui.test.mjs`. При изменении меток полей — обновить ожидания там же.
