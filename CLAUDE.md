# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bitrix24 Excel Import Application — a 7-step wizard for importing CRM data (leads, contacts, companies, deals, tasks, smart processes) from Excel/CSV into Bitrix24. Built with Nuxt 3 frontend + Django backend, deployed via Docker Compose.

---

## Commands

### Environment

```bash
make dev-python        # Start full stack (Docker Compose)
make down              # Stop all containers
make logs              # Stream all container logs
```

### Backend Tests (Django)

```bash
# Run all backend tests
docker exec api-python-worker python manage.py test tests

# Run a specific test module
docker exec api-python-worker python manage.py test tests.test_import_report_metadata

# Working directory inside container: /var/www/api (so the module path is `tests.*`, not `api.tests.*`)
```

Note: There is a pre-existing error (`api.main.utils.decorators` — `RuntimeError: Model class api.main.models.Bitrix24Account doesn't declare an explicit app_label`) that appears in the test output regardless of your changes. It is not caused by import code.

### Frontend Tests (Node.js)

```bash
node --test tests/*.test.mjs            # Run all frontend unit tests
node --test tests/importer-ui.test.mjs  # Run specific test file
```

### Deploying Changes

**Backend** (no rebuild needed — copy file directly into container):
```bash
docker cp backends/python/api/importer/services/report_metadata.py \
  api-python-worker:/var/www/api/importer/services/report_metadata.py
```

**Frontend** (production build — must rebuild and restart):
```bash
docker-compose build frontend && docker-compose up -d frontend
```

---

## Architecture

### Import Wizard Flow (7 Steps)

1. **Source** — upload Excel/CSV file
2. **Structure** — confirm column headers
3. **Field Mapping** — map columns to Bitrix24 fields
4. **Dedup Settings** — configure duplicate detection rules
5. **Validation** — preview parsed data (30-row sample via `SAMPLE_PREVIEW_ROW_LIMIT`)
6. **Dry Run** — test import, shows "Что уйдет в Bitrix24" column
7. **Import Results** — actual import, shows "Что попало в Bitrix24" column

### Import Modes

- **Simple**: file + entity type + basic field mapping only
- **Advanced**: templates, dedup settings, per-row result report with CSV export

### Backend: ImportSession State Machine

`backends/python/api/importer/`

- `models.py` — `ImportSession` (status: pending → running → completed/failed), `ImportTemplate`, `ImportAliasRule`, `ImporterUserRole`
- `tasks.py` — Celery tasks: `run_import_session`, `dry_run`, `retry`, `bulk_attach`, `cleanup_stuck`
- `views.py` — 27 API endpoints (see `urls.py`), `MAX_IMPORT_ROWS=100_000`, `SAMPLE_PREVIEW_ROW_LIMIT=30`
- `services/import_execution.py` — core import loop, calls `build_import_result_report_meta()` for each processed row
- `services/report_metadata.py` — `build_import_result_report_meta()` → builds `report_entity`, `report_title`, `report_record_id` for every result row
- `services/b24_fields.py` — Bitrix24 field definitions, `SMART_PROCESS_ENTITY_TYPE`

Queue: RabbitMQ + Celery when available; falls back to synchronous execution.

### Frontend: Import UI

`frontend/app/`

- `components/ImporterWorkbench.vue` — main 7-step wizard component (~8700 lines)
- `utils/importer-ui.js` — all UI business logic (~3350 lines):
  - `buildFlatDryRunRows()` — builds dry-run table rows; uses `formatImporterFieldLabel()` for field name translation
  - `buildFlatImportRunRows()` — builds import-run table rows; uses `report_title` from backend
  - `formatImporterFieldLabel(fieldId, fieldTitle, t)` — translates Bitrix24 API field IDs via i18n (`importer.field_labels.*`), falling back to the `IMPORTER_FIELD_LABELS` Russian map (`TITLE`→`'Название / заголовок'`, `PHONE`→`'Телефон'`, etc.)
  - `IMPORTER_FIELD_LABELS` — Russian fallback translation map (~line 1500)
  - `dryRunTableColumns` / `importRunTableColumns` — column definitions
- `stores/api.ts` — `useApiStore` for all backend calls
- `components/BulkAttachWizard.vue` — S17 bulk file attach feature

### Supported Import Entity Types

`lead`, `contact`, `company`, `deal`, `task`, `task_comment`, `task_checklist_item`, `task_attachment`, `crm_files_*`, `crm_activity`, `crm_note`, `user`, `department`, `smart_process`

Linked types: `linked_company_contact`, `linked_company_deal`, `linked_contact_deal`, `linked_contact_company`, `linked_deal_contact`, `linked_deal_company`

---

## Critical Rules

### Git

Do not run any git commands without explicit user permission.

### MCP Servers (dev tooling)

Two MCP servers are configured via `.mcp.json` at repo root: **b24-dev-mcp** (HTTP, official Bitrix24 REST API docs — use `bitrix-search` / `bitrix-method-details` to verify methods and field formats instead of guessing) and **playwright** (browser automation for e2e wizard checks; importing inside the portal requires an authenticated portal session). Config lives in `.mcp.json`, not local-scope, to avoid a drive-letter case pitfall in `~/.claude.json`. See [instructions/bitrix24/mcp.md](instructions/bitrix24/mcp.md).

### Bitrix24 Tasks API

`b24pysdk` has no tasks scope. All task-related API calls (`tasks.task.*`) must go through `BitrixAPIRequest` directly — not through the SDK.

### UI Field Label Translation

When displaying Bitrix24 field names in the UI, always translate via `formatImporterFieldLabel(fieldId, fieldTitle, t)` from `importer-ui.js` (pass the i18n `t` for localized labels; without it the function uses the Russian `IMPORTER_FIELD_LABELS` fallback). Never show raw API field IDs (like `TITLE`, `PHONE`) to users.

### Lead Report Title Fallback

`build_report_title()` in `report_metadata.py` uses a fallback chain for leads: `TITLE` → `NAME + LAST_NAME` → `EMAIL` → `PHONE`. Other entities (deal, company, task) use only `TITLE`. This is because Lead supports both a title field and person-name fields — unlike Deal/Contact which only have one naming convention.

### Tests

- Backend: run via `docker exec api-python-worker python manage.py test tests` (not directly with `pytest`)
- Frontend: `node --test tests/importer-ui.test.mjs`
- When changing field label output in `importer-ui.js`, update test expectations in `frontend/tests/importer-ui.test.mjs`
- When changing `build_report_title()` in `report_metadata.py`, update `test_import_report_metadata.py`
