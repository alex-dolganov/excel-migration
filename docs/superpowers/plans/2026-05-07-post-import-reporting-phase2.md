# Post Import Reporting Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the final import report with grouped problem reasons and fast status filters so the user can immediately understand what failed, what was skipped, and what should be retried.

**Architecture:** Reuse the existing `summary.import_run.results` payload and derive richer report state on the frontend. Keep this slice UI-first: no new execution backend, only new helper functions plus final-step rendering in the existing wizard.

**Tech Stack:** Nuxt, Vue, frontend importer helpers/tests, existing final report table

---

## Chunk 1: Frontend Report Helpers

### Task 1: Add grouped problem summary and status filters

**Files:**
- Modify: `frontend/app/utils/importer-ui.js`
- Modify: `frontend/tests/importer-ui.test.mjs`

- [ ] **Step 1: Write the failing tests**

Cover:
- status filters with counts for `all`, `problem`, `created`, `updated`, `skipped`, `cancelled`
- grouped problem summary by repeated error reason
- filtered report rows for the chosen status

- [ ] **Step 2: Run RED**

Run:
`node --test tests/importer-ui.test.mjs`

Expected:
- FAIL because helpers do not exist yet

- [ ] **Step 3: Implement minimal helper functions**

Rules:
- treat `failed`, `skipped`, `cancelled` as problem rows
- group by normalized error text
- include count, rows list, and short label per group

- [ ] **Step 4: Run GREEN**

Run:
`node --test tests/importer-ui.test.mjs`

Expected:
- PASS

---

## Chunk 2: Final Step UI

### Task 2: Render the richer report in `ImporterWorkbench`

**Files:**
- Modify: `frontend/app/components/ImporterWorkbench.vue`

- [ ] **Step 1: Add computed state**

Add:
- active report filter
- filter chips
- grouped problem summary
- filtered import rows

- [ ] **Step 2: Render problem summary block**

Rules:
- show only when there are problem groups
- each group shows reason, count, and row numbers

- [ ] **Step 3: Render quick filters above the final table**

Rules:
- default to `problem` when there are problem rows
- otherwise default to `all`
- table should render filtered rows, not raw all-rows list

- [ ] **Step 4: Keep existing CSV and retry actions intact**

No behavior regressions for:
- report download
- retry failed rows
- cancel status display

---

## Chunk 3: Verification

### Task 3: Run verification and update project files

**Files:**
- Test: `frontend/tests/importer-ui.test.mjs`
- Test: `frontend/tests/index-page-init.test.mjs`
- Modify: `project-daily-log.txt`
- Modify: `project-full-context.txt`

- [ ] **Step 1: Run frontend regression**

Run:
`node --test tests/importer-ui.test.mjs tests/index-page-init.test.mjs`

- [ ] **Step 2: Run frontend production build**

Run from `frontend/`:
`.\\node_modules\\.bin\\nuxt build`

- [ ] **Step 3: Update project context**

Record:
- that final report now has grouped problem reasons and quick filters
- that deeper reporting/history drill-down still remains

---

## Definition Of Done

1. Final report has grouped problem summary.
2. Final report has quick status filters.
3. Table rows change according to selected filter.
4. Existing CSV/retry/cancel behavior remains intact.
5. Frontend tests and build pass.
