# Dedup And Update Existing Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить первый рабочий срез dedup/update existing для импорта, чтобы dry run и run могли отличать новые строки от дублей и безопасно обновлять уже существующие записи.

**Architecture:** Встраиваем dedup-решение в текущий execution pipeline без новой БД-модели. Настройки стратегии храним в `ImportSession.import_settings`, dry run рассчитывает решение по каждой строке без записи, а реальный run использует тот же resolver и либо создает, либо обновляет, либо пропускает найденный дубль.

**Tech Stack:** Django, existing importer views/services, Bitrix24 Python SDK client wrappers, Django test runner

---

## Chunk 1: Backend Dedup Contract

### Task 1: Persist dedup settings in existing importer contract

**Files:**
- Modify: `backends/python/api/importer/views.py`
- Modify: `backends/python/api/tests/test_import_mapping_api.py`

- [ ] **Step 1: Write failing mapping API test for dedup settings persistence**
- [ ] **Step 2: Run the targeted test and confirm RED**
- [ ] **Step 3: Extend `GET/PATCH /api/import-sessions/<id>/mapping` to round-trip dedup settings**
- [ ] **Step 4: Re-run the targeted test and confirm GREEN**

### Task 2: Define first supported dedup shape

**Files:**
- Modify: `backends/python/api/importer/services/import_execution.py`
- Modify: `backends/python/api/tests/test_import_dry_run_api.py`
- Modify: `backends/python/api/tests/test_import_execution_api.py`

- [ ] **Step 1: Write failing dry run test for duplicate decision preview**
- [ ] **Step 2: Write failing execution test for duplicate skip behavior**
- [ ] **Step 3: Write failing execution test for update existing behavior**
- [ ] **Step 4: Run targeted execution tests and confirm RED**

## Chunk 2: Backend Dedup Resolver

### Task 3: Implement duplicate lookup and row action resolver

**Files:**
- Modify: `backends/python/api/importer/services/import_execution.py`

- [ ] **Step 1: Add helpers to normalize dedup settings and supported dedup keys**
- [ ] **Step 2: Add existing-record lookup through current Bitrix24 client scope**
- [ ] **Step 3: Add shared row action resolver for `create`, `update`, `skip`**
- [ ] **Step 4: Keep default behavior backward-compatible as create-only when dedup is not configured**

### Task 4: Reuse resolver in dry run and real execution

**Files:**
- Modify: `backends/python/api/importer/services/import_execution.py`
- Modify: `backends/python/api/importer/views.py`

- [ ] **Step 1: Extend dry run result to show `ready_create`, `ready_update`, `skipped_duplicate`**
- [ ] **Step 2: Extend real import result to count `created_rows`, `updated_rows`, `skipped_rows`, `failed_rows`**
- [ ] **Step 3: Persist new counters into session summary without breaking existing consumers**
- [ ] **Step 4: Re-run targeted tests and confirm GREEN**

## Chunk 3: Optional UI Hook

### Task 5: Add minimal wizard controls for duplicate strategy

**Files:**
- Modify: `frontend/app/stores/api.ts`
- Modify: `frontend/app/components/ImporterWorkbench.vue`
- Modify: `frontend/app/utils/importer-ui.js`
- Modify: `frontend/tests/importer-ui.test.mjs`

- [ ] **Step 1: Add failing UI test for duplicate strategy payload round-trip**
- [ ] **Step 2: Extend API store save mapping call to include dedup settings**
- [ ] **Step 3: Add simple controls for duplicate strategy and keys on the validation step**
- [ ] **Step 4: Re-run frontend tests/build and confirm GREEN**

## Chunk 4: Verification And Logging

### Task 6: Regression and project log

**Files:**
- Modify: `project-daily-log.txt`

- [ ] **Step 1: Run targeted backend regression for mapping, dry run, and execution**
- [ ] **Step 2: If UI was touched, run frontend tests and build**
- [ ] **Step 3: Append outcome, current limitation, and next step to project log**
