# Import Foundation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first backend foundation for Excel Migration by introducing import sessions and saved import templates with minimal API endpoints.

**Architecture:** Add a dedicated Django app for importer domain models instead of mixing importer logic into the starter demo app. Keep portal context denormalized on importer records so the new domain is not tightly coupled to unmanaged Bitrix account tables, while still reading account data from the authenticated request.

**Tech Stack:** Python, Django, MySQL-compatible models, Django test runner, starter-kit auth decorators

---

### Task 1: Create Importer Domain Skeleton

**Files:**
- Create: `backends/python/api/importer/__init__.py`
- Create: `backends/python/api/importer/apps.py`
- Create: `backends/python/api/importer/models.py`
- Create: `backends/python/api/importer/urls.py`
- Create: `backends/python/api/importer/views.py`
- Modify: `backends/python/api/settings.py`
- Modify: `backends/python/api/urls.py`

- [ ] **Step 1: Write the failing model tests**

```python
from django.test import TestCase

from importer.models import ImportSession, ImportTemplate


class ImportSessionModelTest(TestCase):
    def test_create_draft_session(self):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.DRAFT,
            original_filename="leads.xlsx",
        )

        self.assertEqual(session.status, ImportSession.Status.DRAFT)
        self.assertEqual(session.original_filename, "leads.xlsx")


class ImportTemplateModelTest(TestCase):
    def test_template_defaults_to_active(self):
        template = ImportTemplate.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            entity_type=ImportTemplate.EntityType.LEAD,
            name="Lead import default",
            mapping_schema={"TITLE": "title"},
        )

        self.assertTrue(template.is_active)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test importer`
Expected: FAIL with `ModuleNotFoundError` or missing model errors

- [ ] **Step 3: Write minimal implementation**

Create the `importer` Django app with:
- `ImportSession` model
- `ImportTemplate` model
- enum choices for entity type / source format / status
- timestamps and JSON fields for importer metadata
- app registration in `settings.py`
- route include in `urls.py`

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test importer`
Expected: PASS for model tests

- [ ] **Step 5: Commit**

```bash
git add backends/python/api/importer backends/python/api/settings.py backends/python/api/urls.py
git commit -m "feat: add importer domain models"
```

### Task 2: Add Import Sessions API

**Files:**
- Modify: `backends/python/api/importer/views.py`
- Modify: `backends/python/api/importer/urls.py`
- Create: `backends/python/api/importer/tests/test_import_sessions_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from importer.models import ImportSession


class ImportSessionsApiTest(TestCase):
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_list_sessions_returns_portal_sessions_ordered_by_newest(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.DRAFT,
            original_filename="a.xlsx",
        )

        response = self.client.get(
            reverse("importer:sessions"),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 1)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_create_session_returns_created_draft(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        response = self.client.post(
            reverse("importer:sessions"),
            data={
                "entity_type": "lead",
                "source_format": "xlsx",
                "original_filename": "leads.xlsx",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["item"]["status"], "draft")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test importer.tests.test_import_sessions_api`
Expected: FAIL because endpoint does not exist or response contract is missing

- [ ] **Step 3: Write minimal implementation**

Implement:
- `GET /api/import-sessions`
- `POST /api/import-sessions`
- portal scoping by `member_id`
- minimal JSON contract for session list/create

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test importer.tests.test_import_sessions_api`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backends/python/api/importer/views.py backends/python/api/importer/urls.py backends/python/api/importer/tests/test_import_sessions_api.py
git commit -m "feat: add import sessions api"
```

### Task 3: Add Saved Templates Read API

**Files:**
- Modify: `backends/python/api/importer/views.py`
- Modify: `backends/python/api/importer/urls.py`
- Create: `backends/python/api/importer/tests/test_import_templates_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from importer.models import ImportTemplate


class ImportTemplatesApiTest(TestCase):
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_list_only_active_templates_for_current_portal(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        ImportTemplate.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            entity_type=ImportTemplate.EntityType.LEAD,
            name="Lead default",
            mapping_schema={"TITLE": "title"},
        )

        response = self.client.get(
            reverse("importer:templates"),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test importer.tests.test_import_templates_api`
Expected: FAIL because endpoint does not exist

- [ ] **Step 3: Write minimal implementation**

Implement:
- `GET /api/import-templates`
- portal scoping
- active templates only

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test importer.tests.test_import_templates_api`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backends/python/api/importer/views.py backends/python/api/importer/urls.py backends/python/api/importer/tests/test_import_templates_api.py
git commit -m "feat: add import templates api"
```

### Task 4: Verification and Log Update

**Files:**
- Modify: `project-daily-log.txt`

- [ ] **Step 1: Run the importer test suite**

Run: `python manage.py test importer`
Expected: PASS

- [ ] **Step 2: Run the full Django test suite**

Run: `python manage.py test`
Expected: PASS or importer tests pass with known non-importer failures documented

- [ ] **Step 3: Update daily log**

Add an entry describing:
- importer foundation created
- first API endpoints added
- where work stopped
- next implementation step

- [ ] **Step 4: Commit**

```bash
git add project-daily-log.txt
git commit -m "docs: update daily log after import foundation"
```
