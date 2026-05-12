# Dry Run And History Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe dry run before real import and expose recent import history/report context in the Bitrix24 wizard.

**Architecture:** Reuse the existing validated import session as the source of truth. Dry run will build the same row payloads as real import but will not call Bitrix24 write methods, while history will reuse the existing session list endpoint and current counters/status fields for a lightweight report panel.

**Tech Stack:** Django, Nuxt 4, Vue 3, Pinia, Docker Compose, Bitrix24 UI Kit

---

### Task 1: Backend Dry Run Contract

**Files:**
- Modify: `backends/python/api/importer/services/import_execution.py`
- Modify: `backends/python/api/importer/views.py`
- Modify: `backends/python/api/importer/urls.py`
- Create: `backends/python/api/tests/test_import_dry_run_api.py`

- [ ] **Step 1: Write the failing dry run test**
- [ ] **Step 2: Run dry run tests and confirm RED**
- [ ] **Step 3: Implement `POST /api/import-sessions/<id>/dry-run`**
- [ ] **Step 4: Re-run dry run tests and confirm GREEN**

### Task 2: Wizard UI For Dry Run And History

**Files:**
- Modify: `frontend/app/stores/api.ts`
- Modify: `frontend/app/utils/importer-ui.js`
- Modify: `frontend/tests/importer-ui.test.mjs`
- Modify: `frontend/app/components/ImporterWorkbench.vue`

- [ ] **Step 1: Add API store methods for session history and dry run**
- [ ] **Step 2: Add formatter helpers and tests for dry run/history rows**
- [ ] **Step 3: Add dry run button/report block and recent imports panel**
- [ ] **Step 4: Run frontend tests/build and confirm GREEN**

### Task 3: Runtime Verification And Logging

**Files:**
- Modify: `project-daily-log.txt`

- [ ] **Step 1: Restart affected containers**
- [ ] **Step 2: Verify local/public runtime**
- [ ] **Step 3: Append outcome and next step to project log**
