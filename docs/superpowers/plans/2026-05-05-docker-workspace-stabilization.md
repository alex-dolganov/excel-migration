# Docker Workspace Stabilization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `excel-migration-app-clean` the working Docker workspace after the folder move and remove the current dev/prod command inconsistencies.

**Architecture:** Keep the existing single `docker-compose.yml`, but align Make targets with the actual build target variable and Dockerfile stages. For local development, avoid requiring CloudPub when the app is configured for localhost, while preserving the existing CloudPub flow for public tunnel setups.

**Tech Stack:** Docker Compose, Makefile, Python Docker multi-stage build, project runbook docs

---

### Task 1: Fix Docker Command Contracts

**Files:**
- Modify: `makefile`
- Modify: `backends/python/api/Dockerfile`

- [ ] **Step 1: Confirm the broken contract**

Run: `docker compose --profile python --profile db-mysql config --services`
Expected: services resolve, but `make prod-python` still points to a variable not used by compose and Python Dockerfile stage naming is inconsistent with `BUILD_TARGET=production`.

- [ ] **Step 2: Align production targets**

Change:
- `make prod-*` to export `BUILD_TARGET=production`
- Python Dockerfile production stage name from `prod` to `production`

- [ ] **Step 3: Make localhost dev startup independent from CloudPub**

Change:
- `make dev-front`
- `make dev-php`
- `make dev-python`
- `make dev-node`

Behavior:
- if `VIRTUAL_HOST` is localhost / `127.0.0.1`, skip `cloudpub`
- otherwise keep existing CloudPub startup behavior

- [ ] **Step 4: Verify config resolution**

Run: `docker compose config -q`
Expected: exit code `0`

### Task 2: Switch Active Docker Workspace

**Files:**
- Modify: `project-daily-log.txt`

- [ ] **Step 1: Stop the old workspace stack**

Run: `docker compose -f C:\Users\Kade\Work\excel-migration-app\docker-compose.yml down`
Expected: old DB container is removed and ports are released.

- [ ] **Step 2: Start the clean workspace stack**

Run: `make dev-python`
Expected: services start from `excel-migration-app-clean` with MySQL and Python backend.

- [ ] **Step 3: Record the Docker stabilization step**

Add a new daily log entry describing:
- why Docker was adjusted after the folder move
- what was changed
- what is the canonical workspace now

### Task 3: Verification

**Files:**
- No code changes

- [ ] **Step 1: Verify running project origin**

Run: `docker compose ls`
Expected: active project is `excel-migration-app-clean`, not the old folder.

- [ ] **Step 2: Verify service status**

Run: `docker compose ps`
Expected: MySQL and Python API are up from the clean workspace; frontend may also be up depending on selected profiles.

- [ ] **Step 3: Verify production build target**

Run: `BUILD_TARGET=production docker compose --profile python build api-python`
Expected: production image build resolves the `production` stage successfully.
