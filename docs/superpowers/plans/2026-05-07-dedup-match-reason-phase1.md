# Dedup Match Reason Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the user which dedup keys actually matched an existing record in dry-run and final import report rows.

**Architecture:** Extend backend duplicate detection results with a small metadata field describing matched dedup keys. Keep the slice narrow: JSON/UI only, no CSV format changes. Frontend row builders append that reason to the existing details string.

**Tech Stack:** Django, Python importer execution service/API tests, Nuxt/Vue row helpers, node test runner

---

## Chunk 1: Backend Match Metadata

### Task 1: Add failing tests for duplicate match reason

**Files:**
- Modify: `backends/python/api/tests/test_import_dry_run_api.py`
- Modify: `backends/python/api/tests/test_import_execution_api.py`
- Modify: `backends/python/api/importer/services/import_execution.py`

- [x] **Step 1: Update dry-run duplicate tests**

Cover:
- `ready_update` includes `duplicate_match_fields`
- combined lookup keeps both selected keys in order

- [x] **Step 2: Update import duplicate tests**

Cover:
- `skipped_duplicate` includes `duplicate_match_fields`
- `updated` includes `duplicate_match_fields`

- [x] **Step 3: Run RED**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_dry_run_api.ImportDryRunApiTest.test_dry_run_marks_duplicate_rows_for_update_when_dedup_matches_existing_record tests.test_import_dry_run_api.ImportDryRunApiTest.test_dry_run_uses_combined_dedup_filter_when_multiple_fields_are_selected tests.test_import_execution_api.ImportExecutionApiTest.test_run_skips_duplicate_rows_when_dedup_strategy_is_skip tests.test_import_execution_api.ImportExecutionApiTest.test_run_updates_existing_record_when_dedup_strategy_is_update"`

Expected:
- FAIL because duplicate match metadata is not returned yet

- [x] **Step 4: Implement minimal backend metadata**

Rules:
- only include metadata on duplicate-related results
- preserve current result statuses and counters
- do not change CSV export in this slice

- [x] **Step 5: Run GREEN**

Run the same focused tests and confirm PASS.

---

## Chunk 2: Frontend Row Details

### Task 2: Show duplicate reason in dry-run/report details

**Files:**
- Modify: `frontend/tests/importer-ui.test.mjs`
- Modify: `frontend/app/utils/importer-ui.js`

- [x] **Step 1: Update failing frontend helper tests**

Cover:
- `buildDryRunRows` appends `Совпадение: ...`
- `buildImportRunRows` appends `Совпадение: ...`

- [x] **Step 2: Implement minimal formatting helper**

Rules:
- keep existing details text first
- append duplicate reason only when metadata exists

---

## Chunk 3: Verification And Context

### Task 3: Run regression and update project files

**Files:**
- Test: `backends/python/api/tests/test_import_dry_run_api.py`
- Test: `backends/python/api/tests/test_import_execution_api.py`
- Test: `frontend/tests/importer-ui.test.mjs`
- Test: `frontend/tests/index-page-init.test.mjs`
- Modify: `project-daily-log.txt`
- Modify: `project-full-context.txt`

- [x] **Step 1: Run backend regression**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_dry_run_api tests.test_import_execution_api"`

- [x] **Step 2: Run frontend regression**

Run:
`node --test frontend/tests/importer-ui.test.mjs frontend/tests/index-page-init.test.mjs`

- [x] **Step 3: Update context**

Record:
- that dry-run/import rows now explain duplicate matches
- what still remains for richer dedup UX

---

## Definition Of Done

1. Duplicate-related rows expose matched dedup keys in backend JSON.
2. Dry-run and final report rows show that reason to the user.
3. Backend and frontend regressions pass.
