# Linked Company Contact Import Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить MVP сценарий импорта, в котором одна строка Excel создаёт или находит компанию, затем создаёт или находит контакт и автоматически связывает их между собой.

**Architecture:** Новый сценарий реализуется как отдельный `entity_type` внутри текущего одно-сессионного импортера. Backend отдаёт объединённый каталог полей с префиксами `COMPANY__` и `CONTACT__`, а execution layer обрабатывает строку как два payload и выполняет импорт по порядку `company -> contact -> link`.

**Tech Stack:** Django importer API, существующие Bitrix client wrappers, Vue importer workbench, XLSX example templates.

---

### Task 1: Test surface for linked entity

**Files:**
- Modify: `backends/python/api/tests/test_import_field_catalog_api.py`
- Modify: `backends/python/api/tests/test_import_example_templates_api.py`
- Modify: `backends/python/api/tests/test_import_execution_service.py`
- Modify: `backends/python/api/tests/test_import_execution_api.py`
- Modify: `frontend/tests/importer-ui.test.mjs`

- [ ] Step 1: Add failing tests for combined field catalog with prefixed company/contact fields.
- [ ] Step 2: Run targeted backend test and confirm failure is caused by missing linked entity support.
- [ ] Step 3: Add failing tests for linked example template and linked import execution.
- [ ] Step 4: Add failing frontend tests for a new scenario family and mutual exclusivity on step 1.

### Task 2: Backend linked import support

**Files:**
- Modify: `backends/python/api/importer/models.py`
- Modify: `backends/python/api/importer/services/b24_fields.py`
- Modify: `backends/python/api/importer/services/example_templates.py`
- Modify: `backends/python/api/importer/services/import_execution.py`
- Modify: `backends/python/api/importer/views.py`
- Create: `backends/python/api/importer/migrations/*`

- [ ] Step 1: Add new entity type and migration.
- [ ] Step 2: Implement merged Bitrix field catalog with prefixed ids and linked metadata.
- [ ] Step 3: Add example XLSX template for the linked scenario.
- [ ] Step 4: Implement linked dry-run/import helpers with company dedup, contact dedup, and automatic `COMPANY_ID` binding on contact create/update.
- [ ] Step 5: Keep default validation and mapping flow working with the new prefixed fields.

### Task 3: Frontend scenario support

**Files:**
- Modify: `frontend/app/utils/importer-ui.js`
- Modify: `frontend/app/components/ImporterWorkbench.vue`
- Modify: `frontend/app/stores/api.ts` if dedup/entity typing needs extension

- [ ] Step 1: Add a third scenario family `Связанный импорт`.
- [ ] Step 2: Make family selection mutually exclusive with CRM and tasks.
- [ ] Step 3: Reuse the current mapping UI with linked field labels from backend.
- [ ] Step 4: Expose example template metadata and scenario summary for the new type.

### Task 4: Verification

**Files:**
- Modify only if verification reveals defects.

- [ ] Step 1: Run targeted backend tests for field catalog, example template, service execution, and API execution.
- [ ] Step 2: Run targeted frontend tests for importer UI helpers.
- [ ] Step 3: Rebuild frontend production container with `rtk docker compose up -d --build frontend cloudpub`.
- [ ] Step 4: Re-run the most relevant tests after final fixes and only then report completion.
