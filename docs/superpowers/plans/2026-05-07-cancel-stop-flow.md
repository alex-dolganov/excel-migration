# Cancel Stop Flow Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real `cancel / stop flow` so a running import can be stopped before the next row and the session keeps a partial итог with clear cancelled state.

**Architecture:** Keep the current synchronous run API, but make cancellation cooperative: a second request marks the session as `cancelled`, and `execute_import(...)` checks that flag between rows. Persist a partial `summary.import_run` with `cancelled` metadata so history, report and retry can continue working from one session.

**Tech Stack:** Django, Python importer services/tests, Nuxt/Vue importer wizard, existing RBAC and session history UI

---

## Chunk 1: Backend Contract

### Task 1: Add a cancel session endpoint

**Files:**
- Modify: `backends/python/api/importer/urls.py`
- Modify: `backends/python/api/importer/views.py`
- Test: `backends/python/api/tests/test_import_execution_api.py`

- [ ] **Step 1: Write the failing API test**

Cover:
- `POST /api/import-sessions/<id>/cancel`
- only running own session can be cancelled
- response returns `status = cancelled`

- [ ] **Step 2: Run RED**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_execution_api.ImportExecutionApiTest.test_cancel_marks_running_session_as_cancelled"`

Expected:
- FAIL because endpoint does not exist

- [ ] **Step 3: Implement minimal endpoint**

Rules:
- require `sessions.cancel`
- require portal ownership like run
- reject non-running sessions with `400`

- [ ] **Step 4: Run GREEN**

Run the same focused test and confirm PASS.

---

### Task 2: Stop execution cooperatively inside row processing

**Files:**
- Modify: `backends/python/api/importer/services/import_execution.py`
- Modify: `backends/python/api/importer/views.py`
- Test: `backends/python/api/tests/test_import_execution_api.py`

- [ ] **Step 1: Write the failing run-cancel test**

Cover:
- a run starts
- cancel request flips session to `cancelled`
- import stops before remaining rows
- response and persisted summary stay `cancelled`

- [ ] **Step 2: Run RED**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_execution_api.ImportExecutionApiTest.test_run_stops_when_session_was_cancelled_during_execution"`

Expected:
- FAIL because execution ignores cancelled status

- [ ] **Step 3: Add `should_cancel` hook to `execute_import(...)`**

Rules:
- check before starting the next effective row
- return partial results with:
  - `cancelled = true`
  - `cancelled_rows`
  - `remaining_rows`

- [ ] **Step 4: Update run/retry views**

Rules:
- pass a session-status checker into execution
- if result is cancelled, persist:
  - partial `summary.import_run`
  - `status = cancelled`
  - processed/success/fail counters from partial result

- [ ] **Step 5: Run focused GREEN**

Run the cancel-specific backend tests and confirm PASS.

---

## Chunk 2: Frontend Stop Action

### Task 3: Expose stop action in the wizard

**Files:**
- Modify: `frontend/app/stores/api.ts`
- Modify: `frontend/app/components/ImporterWorkbench.vue`
- Modify: `frontend/app/utils/importer-ui.js`
- Test: `frontend/tests/importer-ui.test.mjs`

- [ ] **Step 1: Write the failing frontend test**

Cover one concrete behavior:
- cancelled import rows become retryable in UI state
- cancelled row label is human-readable

- [ ] **Step 2: Run RED**

Run:
`node --test tests/importer-ui.test.mjs`

Expected:
- FAIL because cancelled rows are not surfaced correctly

- [ ] **Step 3: Add cancel session API call and button wiring**

Rules:
- show stop button while `run` or `retry` is in progress
- keep regular run request alive; cancel uses a second request
- show a clear "stop requested" state

- [ ] **Step 4: Update cancelled row/report helpers**

Rules:
- row status label for `cancelled`
- retry state may include cancelled rows so unstarted rows can be resumed from the same session

- [ ] **Step 5: Run GREEN**

Run:
`node --test tests/importer-ui.test.mjs`

Expected:
- PASS

---

## Chunk 3: Verification

### Task 4: Run regression and record result

**Files:**
- Test: `backends/python/api/tests/test_import_execution_api.py`
- Test: `backends/python/api/tests/test_import_permissions_api.py`
- Test: `frontend/tests/importer-ui.test.mjs`
- Test: `frontend/tests/index-page-init.test.mjs`
- Modify: `project-daily-log.txt`
- Modify: `project-full-context.txt`

- [ ] **Step 1: Run backend regression**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_execution_api tests.test_import_permissions_api"`

- [ ] **Step 2: Run frontend regression**

Run:
`node --test tests/importer-ui.test.mjs tests/index-page-init.test.mjs`

- [ ] **Step 3: Run frontend production build**

Run from `frontend/`:
`.\\node_modules\\.bin\\nuxt build`

- [ ] **Step 4: Update project context**

Record:
- what cancel first slice actually supports
- that stop is cooperative between rows, not mid-request interruption
- what remains next after this slice

---

## Definition Of Done

1. There is a real cancel endpoint.
2. A running import can be stopped by a second request.
3. Session status persists as `cancelled`, not `completed`.
4. Partial summary is kept in `summary.import_run`.
5. UI exposes stop while import is running.
6. Cancelled rows are understandable in the final table/history flow.
7. Focused regression and build pass.
