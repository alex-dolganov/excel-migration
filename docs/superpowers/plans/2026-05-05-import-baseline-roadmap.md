# Import Baseline Roadmap Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring Excel Migration to the first genuinely usable baseline where a user can open the app in Bitrix24, upload a file, preview it, adjust structure, see candidate mapping, run validation, and reach a first controlled import flow.

**Architecture:** Continue building on the existing Django `importer` domain and keep the flow session-based: every import runs through `ImportSession`, with metadata, preview, mapping, validation, and execution state all attached to the same record. Split work into two tracks: first stabilize the Bitrix24 app shell so the UI is reliably visible inside the portal, then build the importer wizard slice-by-slice from backend contracts upward.

**Tech Stack:** Nuxt 4, Vue 3, Pinia, Django, MySQL, Bitrix24 JS SDK, Bitrix24 Python SDK, Docker Compose

---

## Baseline Definition

The project should be considered **baseline-ready** only when all of the following are true:

1. The application opens inside Bitrix24 without a blank screen.
2. A user can create an import session for one CRM entity.
3. A user can upload `.xlsx` / `.csv`, inspect preview, and override sheet/header/data row settings.
4. The backend returns live target field metadata and candidate column mapping.
5. A user can manually correct mapping and save it into the session.
6. A user can run validation and see row-level issues before import.
7. A user can launch the first controlled import flow for one entity and get a result summary.

Everything after that is important, but it is **phase 2+**, not the baseline.

---

### Task 1: Stabilize Bitrix24 App Entry

**Why first:** If the app shell is unreliable inside Bitrix24, every next UI step becomes blind debugging.

**Files:**
- Modify: `frontend/app/pages/index.client.vue`
- Modify: `frontend/app/middleware/01.app.page.or.slider.global.ts`
- Modify: `frontend/app/composables/useAppInit.ts`
- Modify: `frontend/app/error.vue`
- Test: `frontend/tests/index-page-init.test.mjs`

- [ ] **Step 1: Keep visible startup state on root page**

Expected behavior:
- no fully blank screen after splash;
- user sees startup stage or explicit error.

- [ ] **Step 2: Verify root page does not fatally disappear on slow B24 init**

Run: `node --test frontend/tests/index-page-init.test.mjs`
Expected: PASS

- [ ] **Step 3: Reproduce in Bitrix24 and document exact remaining failure**

Expected:
- either working starter UI,
- or a concrete visible error/stage to continue from.

**Done when:**
- user can tell what step fails without browser devtools.

---

### Task 2: Add Import Structure Override API

**Why second:** Preview exists already, but user still cannot manually correct the file structure, and mapping depends on that correction.

**Files:**
- Modify: `backends/python/api/importer/models.py`
- Modify: `backends/python/api/importer/views.py`
- Modify: `backends/python/api/importer/urls.py`
- Test: `backends/python/api/tests/test_import_preview_api.py`

- [ ] **Step 1: Write failing tests for manual structure override**

Behavior to cover:
- user can pass `sheet_name`, `header_row`, `data_start_row`;
- preview recalculates `headers` and `preview_rows`;
- session persists updated structure.

- [ ] **Step 2: Run tests and confirm RED**

Run:
`docker compose run --rm api-python python manage.py test tests.test_import_preview_api`

- [ ] **Step 3: Implement minimal PATCH/POST structure update contract**

Target contract:
- `GET /api/import-sessions/<id>/preview`
- `PATCH /api/import-sessions/<id>/preview`

- [ ] **Step 4: Re-run tests and confirm GREEN**

Run:
`docker compose run --rm api-python python manage.py test tests.test_import_preview_api`

**Done when:**
- preview is not only auto-detected but user-correctable.

---

### Task 3: Add Bitrix24 Field Catalog API

**Why third:** Candidate mapping without real target fields is fake progress.

**Files:**
- Create: `backends/python/api/importer/services/b24_fields.py`
- Modify: `backends/python/api/importer/views.py`
- Modify: `backends/python/api/importer/urls.py`
- Test: `backends/python/api/tests/test_import_field_catalog_api.py`

- [ ] **Step 1: Write failing tests for field catalog normalization**

Behavior to cover:
- return portal-scoped CRM field metadata for selected entity;
- normalize standard and custom fields into one response contract;
- include enough metadata for mapping UI:
  - field id
  - title
  - type
  - required flag
  - multiple flag

- [ ] **Step 2: Run RED**

Run:
`docker compose run --rm api-python python manage.py test tests.test_import_field_catalog_api`

- [ ] **Step 3: Implement `GET /api/import-fields?entity_type=lead`**

Minimal contract:
```json
{
  "items": [
    {
      "id": "TITLE",
      "title": "Title",
      "type": "string",
      "required": true,
      "multiple": false
    }
  ]
}
```

- [ ] **Step 4: Run GREEN**

Run:
`docker compose run --rm api-python python manage.py test tests.test_import_field_catalog_api`

**Done when:**
- mapping logic can use real Bitrix24 field metadata, not placeholders.

---

### Task 4: Add Mapping Preview API and Session Persistence

**Why fourth:** This is the first real importer-specific value after upload/preview.

**Files:**
- Modify: `backends/python/api/importer/models.py`
- Modify: `backends/python/api/importer/views.py`
- Modify: `backends/python/api/importer/urls.py`
- Create: `backends/python/api/tests/test_import_mapping_api.py`

- [ ] **Step 1: Write failing tests for mapping preview**

Behavior to cover:
- returns file headers from preview;
- returns target fields from field catalog;
- returns `candidate_mapping` based on simple normalized string matching;
- persists accepted mapping in session.

- [ ] **Step 2: Run RED**

Run:
`docker compose run --rm api-python python manage.py test tests.test_import_mapping_api`

- [ ] **Step 3: Implement minimal mapping endpoints**

Target contract:
- `GET /api/import-sessions/<id>/mapping`
- `PATCH /api/import-sessions/<id>/mapping`

- [ ] **Step 4: Run GREEN**

Run:
`docker compose run --rm api-python python manage.py test tests.test_import_mapping_api`

**Done when:**
- session contains the first usable mapping schema.

---

### Task 5: Build Frontend Wizard Skeleton

**Why fifth:** At this point backend contracts become coherent enough to wire the first real importer UI.

**Files:**
- Create: `frontend/app/pages/importer/index.client.vue`
- Create: `frontend/app/components/importer/SessionCreateCard.vue`
- Create: `frontend/app/components/importer/FileUploadCard.vue`
- Create: `frontend/app/components/importer/PreviewStructureCard.vue`
- Create: `frontend/app/components/importer/MappingCard.vue`
- Create: `frontend/app/stores/importer.ts`
- Modify: `frontend/app/pages/index.client.vue`

- [ ] **Step 1: Create a failing integration check for importer store/helpers**

Minimal target:
- importer store can create a session and load preview.

- [ ] **Step 2: Implement the wizard shell in order**

UI order:
1. entity selection
2. create draft session
3. upload file
4. load preview
5. adjust structure
6. load candidate mapping
7. edit mapping

- [ ] **Step 3: Keep root page simple**

Decision:
- either make `/` redirect to importer wizard,
- or keep starter card with a single “Open Importer” action.

- [ ] **Step 4: Verify in Bitrix24**

Expected:
- not just starter demo buttons,
- but the first importer-specific screen.

**Done when:**
- a user can reach mapping from the UI, not only via backend endpoints.

---

### Task 6: Add Validation Foundation

**Why sixth:** This is the first serious pre-import safety gate and part of the product promise.

**Files:**
- Create: `backends/python/api/importer/services/validation.py`
- Modify: `backends/python/api/importer/views.py`
- Modify: `backends/python/api/importer/models.py`
- Create: `backends/python/api/tests/test_import_validation_api.py`
- Modify: `frontend/app/components/importer/MappingCard.vue`
- Create: `frontend/app/components/importer/ValidationResultsCard.vue`

- [ ] **Step 1: Write failing validation tests**

First baseline checks:
- required fields
- primitive type checks
- email
- phone
- date

- [ ] **Step 2: Implement `POST /api/import-sessions/<id>/validate`**

Expected result:
- summary counts
- row-level issues
- session status transition to `validated` when appropriate

- [ ] **Step 3: Expose validation results in UI**

Expected:
- user sees rows with issues before import.

- [ ] **Step 4: Verify**

Run:
`docker compose run --rm api-python python manage.py test tests.test_import_validation_api`

**Done when:**
- user has a working “validate before import” step.

---

### Task 7: Add First Controlled Import Execution

**Why seventh:** This is the minimum point at which the product stops being a parser and becomes an importer.

**Files:**
- Create: `backends/python/api/importer/services/import_execution.py`
- Modify: `backends/python/api/importer/views.py`
- Modify: `backends/python/api/importer/models.py`
- Create: `backends/python/api/tests/test_import_execution_api.py`
- Modify: `frontend/app/components/importer/ValidationResultsCard.vue`
- Create: `frontend/app/components/importer/ImportRunCard.vue`

- [ ] **Step 1: Write failing execution tests**

First baseline scope:
- one entity only;
- one create-only strategy;
- batch execution without advanced dedup yet.

- [ ] **Step 2: Implement `POST /api/import-sessions/<id>/run`**

Expected:
- session status changes;
- processed/success/failed counters update;
- result summary saved to session.

- [ ] **Step 3: Show result summary in UI**

Expected:
- counts of created / failed rows;
- first import is observable.

- [ ] **Step 4: Verify**

Run:
`docker compose run --rm api-python python manage.py test tests.test_import_execution_api`

**Done when:**
- we have the first real end-to-end import slice.

---

## What Comes After Baseline

Only after baseline is working should we move to:

1. saved import templates;
2. fuzzy matching improvements;
3. dedup strategies and update-existing;
4. dry-run separate from real run;
5. background workers + RabbitMQ;
6. history and downloadable reports;
7. `.xls` support;
8. related entities;
9. file-field bulk import;
10. Harbor-ready release packaging.

---

## Recommended Immediate Next Step

If we continue coding right now, the next rational slice is:

1. finish visible Bitrix24 app startup diagnostics;
2. implement manual structure override API;
3. implement field catalog API;
4. implement mapping preview API.

That gives the first meaningful importer workflow without trying to solve the whole product at once.
