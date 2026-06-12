# frontend/tests/ — unit-тесты (node --test)

Запуск из папки `frontend/`:
```bash
node --test tests/*.test.mjs            # все
node --test tests/importer-ui.test.mjs  # один файл
```

| Файл | Строк | Покрывает |
|---|---|---|
| `importer-ui.test.mjs` | ~3700 | **Основной** — вся логика `app/utils/importer-ui.js`: метки полей, dry-run/import-run строки, колонки. Обновлять при изменении переводов полей |
| `importer-bulk-attach-ui.test.mjs` | ~340 | UI bulk-attach (S17) |
| `importer-simple-mode-ui.test.mjs` | ~130 | Simple-режим импорта |
| `importer-dedup-labels.test.mjs` | ~125 | Метки настроек дедупликации |
| `importer-linked-metadata.test.mjs` | 74 | Метаданные linked-сущностей |
| `task-bulk-attach-ui.test.mjs` | 69 | Bulk-attach для задач |
| `importer-nginx-contract.test.mjs` | 69 | Контракт nginx-конфига (лимиты upload и т.п.) |
| `download-utils.test.mjs` | 50 | `app/utils/downloads.js` |
| `index-page-init.test.mjs` | 49 | `app/utils/index-page-init.js` |
| `importer-upload-limit-ui.test.mjs` | 22 | UI-лимиты загрузки файлов |
