# Task Attachments First Slice Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first usable `task_attachment` import slice so Excel Migration can attach files to existing Bitrix24 tasks from imported rows.

**Architecture:** Keep this inside the existing importer pipeline as one more `entity_type`, following the same static field-catalog pattern already used for `task_comment` and `task_checklist_item`. Isolate file download/upload logic in a dedicated backend service so importer execution stays focused on row processing, while the attachment adapter hides Bitrix24 SDK call-shape differences and download mechanics.

**Tech Stack:** Django, Python, existing importer services/tests, Nuxt frontend selector, Docker Compose

---

## Scope Of The First Slice

This slice is intentionally narrow:

1. Add a new importer entity: `task_attachment`.
2. Support rows with:
   - `TASK_ID` — required Bitrix24 task ID
   - `FILE_URL` — required file source URL
   - `FILE_NAME` — optional display name override
3. Validation must reject empty required fields and malformed rows before run.
4. Import execution must:
   - download the file bytes,
   - upload/attach them through one dedicated adapter,
   - report row-level success/failure in the normal import summary.
5. Frontend must expose the new entity in the selector and naturally reuse existing required-field UX.

Out of scope for this slice:

- parent resolution by external key,
- local filesystem paths,
- multi-file columns in one cell,
- task comments with inline file links,
- archive entities,
- retry/resume semantics for partially uploaded attachment batches.

---

## Chunk 1: Backend Contract

### Task 1: Add the new entity type and static field catalog

**Files:**
- Modify: `backends/python/api/importer/models.py`
- Create: `backends/python/api/importer/migrations/0007_task_attachment_entity_type.py`
- Modify: `backends/python/api/importer/services/b24_fields.py`
- Test: `backends/python/api/tests/test_import_field_catalog_api.py`

- [ ] **Step 1: Write the failing field-catalog test**

Cover:
- `GET /api/import-fields?entity_type=task_attachment`
- returns exactly:
  - `TASK_ID` required integer
  - `FILE_URL` required string
  - `FILE_NAME` optional string

- [ ] **Step 2: Run RED**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_field_catalog_api.ImportFieldCatalogApiTest.test_returns_static_task_attachment_fields_catalog"`

Expected:
- FAIL because `task_attachment` is unsupported

- [ ] **Step 3: Add the new entity type in Django model choices**

Implementation notes:
- extend `EntityType`
- create one new migration only for the choices update

- [ ] **Step 4: Add static field metadata in `b24_fields.py`**

Contract:
- `TASK_ID`
- `FILE_URL`
- `FILE_NAME`

- [ ] **Step 5: Run GREEN**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_field_catalog_api.ImportFieldCatalogApiTest.test_returns_static_task_attachment_fields_catalog"`

Expected:
- PASS

---

### Task 2: Define execution behavior with failing tests

**Files:**
- Create: `backends/python/api/importer/services/task_attachments.py`
- Modify: `backends/python/api/importer/services/import_execution.py`
- Modify: `backends/python/api/tests/test_import_execution_service.py`
- Modify: `backends/python/api/tests/test_import_execution_api.py`

- [ ] **Step 1: Write the failing service-level test for attachment payload flow**

Behavior to cover:
- row with `TASK_ID`, `FILE_URL`, `FILE_NAME`
- downloader returns file bytes + inferred filename
- attachment adapter receives normalized task id and final filename

- [ ] **Step 2: Run RED**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_execution_service.ImportExecutionServiceTest.test_create_task_attachment_uploads_downloaded_file"`

Expected:
- FAIL because task attachment flow does not exist

- [ ] **Step 3: Write the failing API test for importer run**

Behavior to cover:
- `POST /api/import-sessions/<id>/run`
- creates one attachment row successfully
- summary contains `created_rows = 1`
- adapter called with expected task id and file data

- [ ] **Step 4: Run RED**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_execution_api.ImportExecutionApiTest.test_run_creates_task_attachment"`

Expected:
- FAIL because `task_attachment` run path is not implemented

---

## Chunk 2: Attachment Service

### Task 3: Extract download and Bitrix attach adapter into a dedicated service

**Files:**
- Create: `backends/python/api/importer/services/task_attachments.py`
- Modify: `backends/python/api/importer/services/__init__.py`

- [ ] **Step 1: Create `download_attachment_source(...)` helper**

Responsibilities:
- fetch bytes from `FILE_URL`
- derive content type if available
- derive fallback file name from URL when `FILE_NAME` is empty
- raise a clean `ValueError` for inaccessible or empty downloads

- [ ] **Step 2: Create `attach_file_to_task(...)` helper**

Responsibilities:
- accept `account`, `task_id`, `file_name`, `content_bytes`
- hide Bitrix SDK method-call differences behind one adapter
- return a normalized result payload

- [ ] **Step 3: Keep SDK specifics isolated to this file**

Rule:
- do not spread attachment-specific call-shape guessing through `import_execution.py`

- [ ] **Step 4: Re-run service RED test until it fails for the expected missing execution path only**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_execution_service.ImportExecutionServiceTest.test_create_task_attachment_uploads_downloaded_file"`

Expected:
- still FAIL, but now only because importer execution does not yet call the helper

---

### Task 4: Implement task attachment import execution

**Files:**
- Modify: `backends/python/api/importer/services/import_execution.py`
- Modify: `backends/python/api/importer/services/validation.py`

- [ ] **Step 1: Add `task_attachment` execution branch**

Rules:
- parse `TASK_ID` as positive integer
- require non-empty `FILE_URL`
- resolve file name:
  - prefer `FILE_NAME`
  - otherwise fallback to downloaded source name

- [ ] **Step 2: Reuse the dedicated attachment service**

Do:
- download through helper
- attach through helper
- keep row-level error handling consistent with existing importer run

- [ ] **Step 3: Add validation rules for attachment rows**

Minimum:
- `TASK_ID` required, positive integer
- `FILE_URL` required, non-empty

- [ ] **Step 4: Run focused tests**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_execution_service.ImportExecutionServiceTest.test_create_task_attachment_uploads_downloaded_file tests.test_import_execution_api.ImportExecutionApiTest.test_run_creates_task_attachment"`

Expected:
- PASS

---

## Chunk 3: Frontend Exposure

### Task 5: Expose the new entity in the wizard

**Files:**
- Modify: `frontend/app/components/ImporterWorkbench.vue`
- Modify: `frontend/tests/importer-ui.test.mjs`

- [ ] **Step 1: Write the failing frontend test**

Behavior to cover:
- entity selector includes `task_attachment`
- label is visible as `Вложения задач`

- [ ] **Step 2: Run RED**

Run:
`node --test frontend/tests/importer-ui.test.mjs`

Expected:
- FAIL because selector item is absent

- [ ] **Step 3: Add selector option in `ImporterWorkbench.vue`**

Rule:
- do not add custom attachment-specific UI yet
- reuse current required-field summary, mapping table, validation flow

- [ ] **Step 4: Run GREEN**

Run:
`node --test frontend/tests/importer-ui.test.mjs`

Expected:
- PASS

---

## Chunk 4: Regression And Verification

### Task 6: Run importer regression

**Files:**
- Test: `backends/python/api/tests/test_import_field_catalog_api.py`
- Test: `backends/python/api/tests/test_import_validation_api.py`
- Test: `backends/python/api/tests/test_import_execution_service.py`
- Test: `backends/python/api/tests/test_import_execution_api.py`
- Test: `frontend/tests/importer-ui.test.mjs`
- Modify: `project-daily-log.txt`

- [ ] **Step 1: Run focused backend regression**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_field_catalog_api tests.test_import_validation_api tests.test_import_execution_service tests.test_import_execution_api"`

Expected:
- PASS

- [ ] **Step 2: Run frontend regression**

Run:
`node --test frontend/tests/importer-ui.test.mjs frontend/tests/index-page-init.test.mjs`

Expected:
- PASS

- [ ] **Step 3: Run frontend production build**

Run from `frontend/`:
`.\\node_modules\\.bin\\nuxt build`

Expected:
- successful build

- [ ] **Step 4: Append outcome to project log**

Record:
- what first attachment slice supports,
- what remains intentionally out of scope,
- exact next gap after this slice.

---

## Definition Of Done

The slice is complete only when:

1. `task_attachment` appears in entity selection.
2. Field catalog returns required metadata for attachment rows.
3. Validation rejects empty `TASK_ID` / `FILE_URL`.
4. Import run can successfully attach one file to one task through the adapter.
5. Import result summary stays compatible with current history UI.
6. Backend focused regression passes.
7. Frontend tests and build pass.

---

## Immediate Next Step After This Slice

After `task_attachment` is working, the next adjacent block should be:

1. richer attachment sources:
   - multi-file cells
   - better file name rules
   - better download failure messages
2. parent references by external key for task subtree
3. archived entities

