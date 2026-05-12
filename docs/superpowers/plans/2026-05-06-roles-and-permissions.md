# Roles And Permissions Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить в Excel Migration базовую модель прав доступа, чтобы в одном портале можно было безопасно разделить администраторов, операторов импорта и пользователей только для просмотра.

**Architecture:** Берем уже существующий сигнал Bitrix24 `is_b24_user_admin` как верхний уровень доверия и поверх него добавляем локальный RBAC приложения на уровне портала. Права проверяются на backend перед каждым действием, а frontend только отражает доступные действия и прячет запрещенные кнопки. Владение import session опирается на уже существующее поле `created_by_b24_user_id`.

**Tech Stack:** Django, existing Bitrix24 auth flow, Nuxt/Vue, existing importer API/tests.

---

## File Structure

- Modify: `backends/python/api/importer/models.py`
  - хранение роли пользователя внутри портала;
- Create: `backends/python/api/importer/services/permissions.py`
  - единая матрица ролей и проверок;
- Modify: `backends/python/api/importer/views.py`
  - endpoints ролей и защита существующих importer actions;
- Modify: `backends/python/api/importer/urls.py`
  - routes для чтения и управления ролями;
- Create: `backends/python/api/tests/test_import_permissions_api.py`
  - backend-покрытие прав;
- Modify: `frontend/app/stores/user.ts`
  - текущая app role и список разрешений;
- Modify: `frontend/app/stores/api.ts`
  - запросы current permissions / roles management;
- Modify: `frontend/app/components/ImporterWorkbench.vue`
  - скрытие и disable действий по правам;
- Modify: `frontend/app/pages/slider/app-options.client.vue`
  - admin-only управление ролями;
- Create: `frontend/tests/importer-permissions-ui.test.mjs`
  - UI regression на доступность действий.

## Target RBAC Model

- `portal_admin`
  - любой пользователь Bitrix24 с `is_b24_user_admin=true`;
  - полный доступ;
  - управляет ролями других пользователей.
- `operator`
  - может создавать import session, загружать файлы, настраивать mapping, validation, dry run и запускать импорт;
  - видит историю и шаблоны;
  - не управляет ролями.
- `viewer`
  - только просмотр истории, preview, dry run result и отчетов;
  - не может менять mapping и запускать импорт.

## Permission Matrix

- `roles.manage`
  - только `portal_admin`
- `templates.manage`
  - `portal_admin`, `operator`
- `sessions.create`
  - `portal_admin`, `operator`
- `sessions.edit_own`
  - `portal_admin`, `operator`
- `sessions.view`
  - `portal_admin`, `operator`, `viewer`
- `sessions.run`
  - `portal_admin`, `operator`
- `sessions.cancel`
  - `portal_admin`, `operator`
- `reports.view`
  - `portal_admin`, `operator`, `viewer`

## Chunk 1: Backend Role Storage

### Task 1: Add local role model

**Files:**
- Modify: `backends/python/api/importer/models.py`
- Test: `backends/python/api/tests/test_import_permissions_api.py`

- [ ] Step 1: Write failing tests for role resolution inside one portal.
- [ ] Step 2: Add `ImporterUserRole` model with fields:
  - `portal_member_id`
  - `portal_domain`
  - `b24_user_id`
  - `role`
  - `granted_by_b24_user_id`
  - timestamps
- [ ] Step 3: Add uniqueness on `(portal_member_id, b24_user_id)`.
- [ ] Step 4: Create and check migration.
- [ ] Step 5: Run backend tests for model and migration behavior.

### Task 2: Implement permission service

**Files:**
- Create: `backends/python/api/importer/services/permissions.py`
- Test: `backends/python/api/tests/test_import_permissions_api.py`

- [ ] Step 1: Write failing tests for `resolve_role()` and `has_permission()`.
- [ ] Step 2: Implement rule:
  - if `account.is_b24_user_admin` -> role `portal_admin`;
  - else use `ImporterUserRole`;
  - else deny by default.
- [ ] Step 3: Add helper for ownership check on `ImportSession.created_by_b24_user_id`.
- [ ] Step 4: Run targeted tests.

## Chunk 2: Backend API Enforcement

### Task 3: Add roles API

**Files:**
- Modify: `backends/python/api/importer/views.py`
- Modify: `backends/python/api/importer/urls.py`
- Test: `backends/python/api/tests/test_import_permissions_api.py`

- [ ] Step 1: Write failing tests for:
  - current user permissions endpoint;
  - roles list endpoint;
  - role upsert endpoint;
  - deny for non-admin.
- [ ] Step 2: Add endpoints:
  - `GET /api/import-permissions/me`
  - `GET /api/import-roles`
  - `POST /api/import-roles`
- [ ] Step 3: Return compact payload:
  - current role
  - permissions array
  - user id
  - portal admin flag
- [ ] Step 4: Run backend tests.

### Task 4: Protect existing importer actions

**Files:**
- Modify: `backends/python/api/importer/views.py`
- Test: `backends/python/api/tests/test_import_permissions_api.py`

- [ ] Step 1: Write failing tests for forbidden actions by `viewer`.
- [ ] Step 2: Gate existing actions:
  - session create
  - upload
  - preview structure save
  - mapping save
  - validation
  - dry run
  - run import
  - template save/apply where needed
- [ ] Step 3: Keep session list/report readable for `viewer`.
- [ ] Step 4: Run importer regression tests.

## Chunk 3: Frontend Permission Awareness

### Task 5: Load current permissions in UI

**Files:**
- Modify: `frontend/app/stores/user.ts`
- Modify: `frontend/app/stores/api.ts`
- Modify: `frontend/app/composables/useAppInit.ts`
- Test: `frontend/tests/importer-permissions-ui.test.mjs`

- [ ] Step 1: Write failing frontend tests for permission-based UI state.
- [ ] Step 2: Add API method to fetch current import permissions.
- [ ] Step 3: Store `importerRole` and `importerPermissions` in user store.
- [ ] Step 4: Load them during app init.
- [ ] Step 5: Run frontend tests.

### Task 6: Restrict buttons and steps in wizard

**Files:**
- Modify: `frontend/app/components/ImporterWorkbench.vue`
- Test: `frontend/tests/importer-permissions-ui.test.mjs`

- [ ] Step 1: Disable or hide edit/run actions for `viewer`.
- [ ] Step 2: Keep history and reports visible for `viewer`.
- [ ] Step 3: Show clear empty-state text when user has read-only access.
- [ ] Step 4: Run frontend tests and build.

### Task 7: Add admin role management screen

**Files:**
- Modify: `frontend/app/pages/slider/app-options.client.vue`
- Test: `frontend/tests/importer-permissions-ui.test.mjs`

- [ ] Step 1: Add a simple roles block to app options.
- [ ] Step 2: Allow admin to assign `operator` or `viewer` by Bitrix user ID.
- [ ] Step 3: Show current assignments for the portal.
- [ ] Step 4: Run UI regression and build.

## Chunk 4: Final Verification

### Task 8: Regression and docs

**Files:**
- Modify: `project-daily-log.txt`
- Modify: `project-full-context.txt`

- [ ] Step 1: Run backend regression for importer APIs.
- [ ] Step 2: Run frontend permission tests.
- [ ] Step 3: Run frontend build.
- [ ] Step 4: Update daily log and full context with final RBAC behavior.

## Notes

- Не вводить сложные кастомные ACL по каждому полю на первом проходе.
- Не синхронизировать всех сотрудников портала в локальную БД заранее.
- Назначение ролей хранить только внутри конкретного портала.
- В будущем можно расширить модель до `auditor` и прав по сущностям (`lead`, `contact`, `company`, `deal`) без слома API, если permission-коды останутся строковыми.
