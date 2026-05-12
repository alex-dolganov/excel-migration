# Custom Fields First Slice Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first usable slice of custom field type support so `multiple=true` custom Bitrix24 fields validate and import correctly from Excel values.

**Architecture:** Keep the change inside the existing importer pipeline. Extend backend normalization/validation/import execution to treat multi-value custom fields as arrays and validate each split item using the field metadata already loaded from Bitrix24.

**Tech Stack:** Django, Python, existing importer services and unit tests

---

### Task 1: Define expected behavior with tests

**Files:**
- Modify: `backends/python/api/tests/test_import_validation_service.py`
- Modify: `backends/python/api/tests/test_import_execution_service.py`

- [ ] **Step 1: Write the failing validation test**

Add a test proving a custom multi-value list field accepts `Alpha; Beta` only when both values map to target list items.

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test tests.test_import_validation_service`

- [ ] **Step 3: Write the failing payload test**

Add a test proving a custom multi-value field is exported as an array of resolved values instead of one raw string.

- [ ] **Step 4: Run test to verify it fails**

Run: `python manage.py test tests.test_import_execution_service`

### Task 2: Implement minimal backend support

**Files:**
- Modify: `backends/python/api/importer/services/validation.py`
- Modify: `backends/python/api/importer/services/import_execution.py`

- [ ] **Step 1: Add shared splitting logic for multi-value cells**
- [ ] **Step 2: Validate each split item according to field type and enum metadata**
- [ ] **Step 3: Build array payloads for non-CRM custom multi-value fields**
- [ ] **Step 4: Keep existing single-value and CRM multifield behavior unchanged**

### Task 3: Verify regression surface

**Files:**
- Test: `backends/python/api/tests/test_import_validation_service.py`
- Test: `backends/python/api/tests/test_import_execution_service.py`
- Test: `backends/python/api/tests/test_import_mapping_api.py`
- Test: `backends/python/api/tests/test_import_validation_api.py`
- Test: `backends/python/api/tests/test_import_dry_run_api.py`
- Test: `backends/python/api/tests/test_import_execution_api.py`
- Test: `backends/python/api/tests/test_import_templates_api.py`

- [ ] **Step 1: Run targeted tests**

Run: `python manage.py test tests.test_import_validation_service tests.test_import_execution_service`

- [ ] **Step 2: Run importer regression**

Run: `python manage.py test tests.test_import_mapping_api tests.test_import_validation_api tests.test_import_dry_run_api tests.test_import_execution_api tests.test_import_templates_api tests.test_import_validation_service tests.test_import_execution_service`

- [ ] **Step 3: Update project logs briefly if behavior is confirmed**
