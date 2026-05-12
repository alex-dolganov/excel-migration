# Dedup Combined Keys Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make duplicate detection respect the full set of selected dedup keys instead of matching on the first selected field that happens to return a record.

**Architecture:** Keep the current dedup configuration shape (`strategy` + `fields`) but change lookup semantics in the backend. When several dedup fields are selected and have usable values in the row payload, build one combined Bitrix filter from all of them. This makes `skip/update` safer and better aligned with user expectations.

**Tech Stack:** Django, Python importer services, existing dry-run/import API tests, Nuxt/Vue copy update

---

## Chunk 1: Backend Combined Dedup Lookup

### Task 1: Cover combined-key behavior in API tests

**Files:**
- Modify: `backends/python/api/tests/test_import_dry_run_api.py`
- Modify: `backends/python/api/tests/test_import_execution_api.py`
- Modify: `backends/python/api/importer/services/import_execution.py`

- [x] **Step 1: Write the failing dry-run test**

Cover:
- dedup fields `EMAIL` + `PHONE`
- combined filter finds an existing record
- backend performs one combined lookup instead of two single-field fallbacks

- [x] **Step 2: Write the failing import test**

Cover:
- dedup fields `EMAIL` + `PHONE`
- only a single-field `EMAIL` duplicate exists
- import must create a new record instead of treating that row as a duplicate

- [x] **Step 3: Run RED**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_dry_run_api.ImportDryRunApiTest.test_dry_run_uses_combined_dedup_filter_when_multiple_fields_are_selected tests.test_import_execution_api.ImportExecutionApiTest.test_run_does_not_use_single_field_duplicate_when_multiple_dedup_fields_are_selected"`

Expected:
- FAIL because current lookup logic iterates fields one-by-one

- [x] **Step 4: Implement minimal dedup lookup change**

Rules:
- keep existing `create/skip/update` strategies
- if multiple selected dedup fields have values, query Bitrix with one combined filter
- if only one selected field has a value, keep single-field lookup behavior
- do not broaden supported fields in this slice

- [x] **Step 5: Run GREEN**

Run the same focused tests and confirm PASS.

---

## Chunk 2: UI Clarity

### Task 2: Clarify dedup key semantics in step copy

**Files:**
- Modify: `frontend/app/components/ImporterWorkbench.vue`

- [x] **Step 1: Update helper copy**

Clarify:
- selected dedup keys work together
- duplicate match becomes stricter when several keys are selected

---

## Chunk 3: Verification And Context

### Task 3: Run regression and update project files

**Files:**
- Test: `backends/python/api/tests/test_import_dry_run_api.py`
- Test: `backends/python/api/tests/test_import_execution_api.py`
- Modify: `project-daily-log.txt`
- Modify: `project-full-context.txt`

- [x] **Step 1: Run backend regression**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_dry_run_api tests.test_import_execution_api"`

- [x] **Step 2: Update context**

Record:
- combined dedup lookup semantics
- remaining gaps for richer dedup

---

## Definition Of Done

1. Multiple selected dedup keys are treated as one combined lookup when values are present.
2. Single-field partial matches no longer trigger wrong `skip/update` when several keys were selected.
3. Dry-run and import regression tests pass.
