# Example XLSX Templates Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user download a ready-made Excel example template for the currently selected import entity directly from step 1 of the wizard.

**Architecture:** Add a backend endpoint that returns a generated `.xlsx` file based on static per-entity sample definitions. Then add a step-1 frontend action that downloads the template for the currently selected scenario. Keep the first slice simple: one sheet, headers + one example row, no server-side persistence.

**Tech Stack:** Django, Python XLSX zip/xml generation, Nuxt/Vue importer workbench, existing API store download pattern

---

## Chunk 1: Backend Example Template Download

### Task 1: Add failing tests and endpoint

**Files:**
- Create: `backends/python/api/tests/test_import_example_templates_api.py`
- Create: `backends/python/api/importer/services/example_templates.py`
- Modify: `backends/python/api/importer/views.py`
- Modify: `backends/python/api/importer/urls.py`

- [x] **Step 1: Write the failing API tests**

Cover:
- operator/admin can download `.xlsx` for selected `entity_type`
- workbook contains expected headers and one example row for at least:
  - `deal`
  - `task`
  - `task_checklist_item`
- viewer cannot download template
- unknown `entity_type` returns 400

- [x] **Step 2: Run RED**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_example_templates_api"`

Expected:
- FAIL because endpoint/service do not exist yet

- [x] **Step 3: Implement minimal example-template service**

Rules:
- generate real `.xlsx`, not csv
- one sheet only
- row 1 = headers
- row 2 = example values
- support all currently imported entity types

- [x] **Step 4: Implement download endpoint**

Rules:
- require auth
- require `sessions.create`
- return correct content type and filename

- [x] **Step 5: Run GREEN**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_example_templates_api"`

---

## Chunk 2: Frontend Download Action

### Task 2: Add step-1 template download button

**Files:**
- Modify: `frontend/app/utils/importer-ui.js`
- Modify: `frontend/app/stores/api.ts`
- Modify: `frontend/app/components/ImporterWorkbench.vue`
- Modify: `frontend/tests/importer-ui.test.mjs`

- [x] **Step 1: Add failing helper test if a new helper is introduced**

Cover:
- template download info reflects selected entity/scenario

- [x] **Step 2: Implement download method and button**

Rules:
- button lives on step 1 near file selection
- button downloads template for current `entityType`
- use same blob download pattern as CSV report

---

## Chunk 3: Verification And Context

### Task 3: Run regression and update project files

**Files:**
- Test: `backends/python/api/tests/test_import_example_templates_api.py`
- Test: `frontend/tests/importer-ui.test.mjs`
- Test: `frontend/tests/index-page-init.test.mjs`
- Modify: `project-daily-log.txt`
- Modify: `project-full-context.txt`

- [x] **Step 1: Run backend regression**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_example_templates_api"`

- [x] **Step 2: Run frontend regression**

Run:
`node --test frontend/tests/importer-ui.test.mjs frontend/tests/index-page-init.test.mjs`

- [x] **Step 3: Try frontend build**

Run:
`node .\\node_modules\\nuxt\\bin\\nuxt.mjs build`

Expected:
- either PASS
- or same known local `lightningcss` environment failure, recorded honestly

- [x] **Step 4: Update context**

Record:
- that step 1 can now download example Excel templates per entity/scenario
- what still remains for richer template onboarding

---

## Definition Of Done

1. User can download a real `.xlsx` example file for the selected import entity.
2. Deal/task/checklist/etc. templates differ in headers/example row.
3. Step 1 exposes the action clearly.
4. Backend and frontend regressions pass.
