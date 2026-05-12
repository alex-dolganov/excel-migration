# Import Templates Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user save the current import mapping as a reusable template and apply an existing template to a new import session from the Bitrix24 wizard.

**Architecture:** Reuse the existing `ImportTemplate` model and extend the current `/api/import-templates` contract so templates stay portal-scoped and entity-scoped. Keep the feature session-based: saving a template serializes the current session mapping/structure, applying a template writes those settings back into the current `ImportSession`, then reuses the existing preview/mapping flow.

**Tech Stack:** Django, Nuxt 4, Vue 3, Pinia, Bitrix24 UI Kit, Docker Compose

---

### Task 1: Backend Template Contracts

**Files:**
- Modify: `backends/python/api/importer/views.py`
- Modify: `backends/python/api/importer/urls.py`
- Test: `backends/python/api/tests/test_import_templates_api.py`

- [ ] **Step 1: Write failing tests for template save/apply**
- [ ] **Step 2: Run template API tests and confirm RED**
- [ ] **Step 3: Implement `GET/POST /api/import-templates` and `POST /api/import-sessions/<id>/apply-template`**
- [ ] **Step 4: Re-run template tests and confirm GREEN**

### Task 2: Wizard Integration

**Files:**
- Modify: `frontend/app/stores/api.ts`
- Modify: `frontend/app/components/ImporterWorkbench.vue`
- Test: `frontend/tests/importer-ui.test.mjs`

- [ ] **Step 1: Add API store methods for template list/save/apply**
- [ ] **Step 2: Add template controls into the mapping step of the wizard**
- [ ] **Step 3: Allow applying a template to current session and refreshing preview/mapping**
- [ ] **Step 4: Run frontend tests/build and confirm GREEN**

### Task 3: Runtime Verification And Logging

**Files:**
- Modify: `project-daily-log.txt`

- [ ] **Step 1: Restart affected containers**
- [ ] **Step 2: Verify local/public runtime**
- [ ] **Step 3: Append implementation result and next step to project log**
