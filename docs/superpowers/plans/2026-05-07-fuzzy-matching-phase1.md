# Fuzzy Matching Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve auto-mapping so the importer can suggest Bitrix24 fields for close-but-not-exact column names instead of only exact normalized title/id matches.

**Architecture:** Extend backend candidate mapping with a lightweight fuzzy scorer over normalized header/field title/id tokens. Keep the first slice narrow: better suggestions first, optional lightweight UI transparency second.

**Tech Stack:** Django, Python mapping service/tests, existing importer mapping API, frontend mapping table

---

## Chunk 1: Backend Fuzzy Suggestions

### Task 1: Add failing tests for fuzzy candidate mapping

**Files:**
- Modify: `backends/python/api/tests/test_import_mapping_api.py`
- Modify: `backends/python/api/importer/services/mapping.py`

- [x] **Step 1: Write the failing API test**

Cover:
- headers like `Lead Name`, `Mobile phone`, `Town`
- candidate mapping still resolves to `TITLE`, `PHONE`, `UF_CRM_CITY`

- [x] **Step 2: Run RED**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_mapping_api.ImportMappingApiTest.test_mapping_returns_fuzzy_candidate_mapping_for_close_headers"`

Expected:
- FAIL because current matching only handles exact normalized matches

- [x] **Step 3: Implement minimal fuzzy scorer**

Rules:
- exact normalized match still wins
- fuzzy match should remain conservative
- avoid duplicate assignment of one field to multiple headers

- [x] **Step 4: Run GREEN**

Run the focused test again and confirm PASS.

---

## Chunk 2: Optional UI Transparency

### Task 2: Surface exact vs fuzzy suggestion type in mapping UI

**Files:**
- Modify: `frontend/app/utils/importer-ui.js`
- Modify: `frontend/app/components/ImporterWorkbench.vue`
- Modify: `frontend/tests/importer-ui.test.mjs`

- [x] **Step 1: Add failing frontend test if exposing metadata**

Cover:
- candidate row can carry `autoMatchType`
- UI helper keeps exact/fuzzy distinction

- [x] **Step 2: Implement minimal chip**

Rules:
- only for auto candidate state, not for saved mapping
- labels: `Точное` / `Похожее`

---

## Chunk 3: Verification

### Task 3: Run regression and update project files

**Files:**
- Test: `backends/python/api/tests/test_import_mapping_api.py`
- Test: `frontend/tests/importer-ui.test.mjs`
- Test: `frontend/tests/index-page-init.test.mjs`
- Modify: `project-daily-log.txt`
- Modify: `project-full-context.txt`

- [x] **Step 1: Run backend mapping regression**

Run:
`docker exec api sh -lc "cd /var/www/api && python manage.py test tests.test_import_mapping_api"`

- [x] **Step 2: Run frontend regression if UI metadata was added**

Run:
`node --test tests/importer-ui.test.mjs tests/index-page-init.test.mjs`

- [x] **Step 3: Update context**

Record:
- that auto-mapping is no longer exact-only
- what still remains for fuller fuzzy experience

---

## Definition Of Done

1. Close headers auto-map without exact equality.
2. Exact match priority is preserved.
3. Backend mapping tests pass.
4. If UI metadata was added, frontend tests pass and build is either green or blocked only by local environment.
