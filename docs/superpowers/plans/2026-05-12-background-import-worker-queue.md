# Background Import Worker Queue Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move import execution and retry execution out of the request/response cycle into a RabbitMQ-backed worker flow for the Python backend.

**Architecture:** Keep validation, dry-run, result merging, and cancellation semantics in the existing importer domain, but move long-running `run` and `retry-failed` execution into Celery tasks. The HTTP API should enqueue work, mark the session as running, and let the frontend poll session state until the worker writes the final summary.

**Tech Stack:** Django, Celery, RabbitMQ, Vue/Nuxt, existing importer services.

---

### Task 1: Queue-Aware API Contract

**Files:**
- Modify: `backends/python/api/tests/test_import_execution_api.py`
- Modify: `backends/python/api/tests/test_import_sessions_api.py`

- [x] Add failing API tests for queue-enabled `run` and `retry-failed`.
- [x] Add failing API test for fetching a single session during polling.
- [x] Run targeted Django tests and confirm the new cases fail for the expected reason.

### Task 2: Background Execution Layer

**Files:**
- Create: `backends/python/api/celery.py`
- Create: `backends/python/api/importer/tasks.py`
- Create: `backends/python/api/importer/services/background_jobs.py`
- Modify: `backends/python/api/__init__.py`
- Modify: `backends/python/api/requirements.txt`

- [x] Add Celery app configuration bound to `RABBITMQ_DSN`.
- [x] Add importer tasks for `run` and `retry-failed`.
- [x] Add a service layer that decides between enqueue vs sync fallback.
- [x] Run targeted tests to confirm queue dispatch code passes.

### Task 3: Import Execution Refactor

**Files:**
- Modify: `backends/python/api/importer/views.py`

- [x] Refactor synchronous import/retry logic into reusable functions callable from both views and tasks.
- [x] Update API views to return an accepted/running snapshot when the queue is enabled.
- [x] Preserve synchronous fallback when RabbitMQ is disabled.
- [x] Run targeted importer API tests and confirm green.

### Task 4: Frontend Polling Flow

**Files:**
- Modify: `frontend/app/stores/api.ts`
- Modify: `frontend/app/components/ImporterWorkbench.vue`

- [x] Add API call for a single session snapshot.
- [x] Add polling during queued/running import and retry flows.
- [x] Keep current UI behavior for synchronous fallback and final result rendering.
- [x] Run focused verification for the Vue code path.

### Task 5: Local Worker Runtime

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `backends/python/api/Dockerfile`

- [x] Add a dedicated Python worker service using the same image.
- [x] Ensure queue env wiring is explicit for local development.
- [x] Verify the compose configuration still parses correctly.
