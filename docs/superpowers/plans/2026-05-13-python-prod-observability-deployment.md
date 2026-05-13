# Python Prod Observability Deployment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the Python backend to a production-ready deployment shape for the target cloud environment: external MySQL, Nginx-facing runtime, RabbitMQ-backed background jobs, OpenTelemetry-based observability, portal-level debug controls, and internal error ticket forwarding through `mptools`.

**Architecture:** Keep `gunicorn` as the Python application server behind Nginx for synchronous HTTP traffic, and keep long-running importer work in `Celery + RabbitMQ`. Do not treat `gunicorn` as a queue transport: file uploads still arrive over HTTP, are persisted by Django, and only then trigger background execution through the queue layer. Observability and support hooks must be environment-driven, safe to disable, and compatible with cloud deployment where direct log access is unavailable.

**Tech Stack:** Django, Gunicorn, Celery, RabbitMQ, MySQL, Nginx, OpenTelemetry, Grafana, Vue/Nuxt, Docker Compose.

---

## Chunk 1: Runtime Topology And Production Contracts

### Task 1: Lock the production runtime model

**Files:**
- Modify: `docs/superpowers/plans/2026-05-12-background-import-worker-queue.md`
- Create: `docs/superpowers/plans/2026-05-13-python-prod-observability-deployment.md`
- Reference: `требования и описание.txt`
- Reference: `instructions/python/knowledge.md`

- [ ] **Step 1: Record the runtime decision explicitly**

Document in this plan and in the queue plan:
- `gunicorn` handles HTTP requests only.
- `Celery + RabbitMQ` handles background importer jobs.
- `Nginx` sits in front of the Python app in cloud deployment.
- file upload is accepted by Django first, then queued after session/file persistence.

- [ ] **Step 2: Write the deployment invariants**

Document these invariants:
- production DB is external `MySQL`;
- queue broker is external `RabbitMQ`;
- reverse proxy is `Nginx`;
- cloud operators do not provide direct application log access;
- all critical diagnostics must be exported through telemetry or support proxy integrations.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-05-12-background-import-worker-queue.md docs/superpowers/plans/2026-05-13-python-prod-observability-deployment.md
git commit -m "docs: define python production runtime topology"
```

## Chunk 2: MySQL-First Production Readiness

### Task 2: Make Python backend explicitly production-ready for external MySQL

**Files:**
- Modify: `backends/python/api/config.py`
- Modify: `backends/python/api/settings.py`
- Modify: `backends/python/api/Dockerfile`
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Test: `backends/python/api/tests/`

- [ ] **Step 1: Add failing configuration checks for MySQL-backed production mode**

Add tests or config assertions that prove:
- Django can boot with MySQL settings from env;
- host, port, DB name, user, password are not hardcoded to local-only defaults in production mode;
- production mode does not depend on PostgreSQL-specific packages or settings.

- [ ] **Step 2: Run the failing checks**

Run:

```bash
docker compose --env-file .env config
docker compose --env-file .env run --rm api-python python manage.py check
```

Expected: current gaps are visible if MySQL config is incomplete.

- [ ] **Step 3: Implement explicit external MySQL configuration support**

Ensure:
- config exposes DB engine/driver selection cleanly;
- production path prefers MySQL;
- local docker profiles can still use postgres/mysql selectively without breaking dev.

- [ ] **Step 4: Verify MySQL mode**

Run:

```bash
docker compose --env-file .env --profile db-mysql up -d database-mysql
docker compose --env-file .env run --rm api-python python manage.py check
docker compose --env-file .env run --rm api-python python manage.py test
```

Expected: backend boots and tests pass against MySQL-compatible configuration.

- [ ] **Step 5: Commit**

```bash
git add backends/python/api/config.py backends/python/api/settings.py backends/python/api/Dockerfile .env.example docker-compose.yml
git commit -m "feat: make python backend production-ready for external mysql"
```

## Chunk 3: Gunicorn, Nginx, And Queue Runtime Separation

### Task 3: Separate HTTP runtime from worker runtime cleanly

**Files:**
- Modify: `backends/python/api/Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `README.md`
- Modify: `instructions/python/knowledge.md`

- [ ] **Step 1: Add failing runtime documentation/tests for split-process expectations**

Document and verify:
- web container starts `gunicorn`;
- worker container starts `celery worker`;
- neither process attempts to replace the other;
- queue-enabled import still works when web and worker run separately.

- [ ] **Step 2: Implement explicit command separation**

Ensure:
- web service command is `gunicorn ...` in production mode;
- worker service command is `celery -A ... worker`;
- optional migration/bootstrap logic does not couple web startup to worker startup.

- [ ] **Step 3: Add Nginx-facing deployment notes**

Document:
- expected upstream port for Python app;
- required proxy headers (`X-Forwarded-*`);
- max upload size alignment between Nginx and Django;
- static/media handling expectations.

- [ ] **Step 4: Verify compose/runtime behavior**

Run:

```bash
docker compose --env-file .env config
docker compose --env-file .env up -d api-python api-python-worker rabbitmq
```

Expected: web and worker start as separate concerns.

- [ ] **Step 5: Commit**

```bash
git add backends/python/api/Dockerfile docker-compose.yml README.md instructions/python/knowledge.md
git commit -m "docs: separate gunicorn http runtime from celery queue runtime"
```

## Chunk 4: OpenTelemetry, Grafana, And Portal-Level Debug Control

### Task 4: Add observability that survives lack of direct log access

**Files:**
- Create: `backends/python/api/otel.py`
- Modify: `backends/python/api/asgi.py`
- Modify: `backends/python/api/wsgi.py`
- Modify: `backends/python/api/config.py`
- Modify: `backends/python/api/main/utils/decorators/log_errors.py`
- Modify: `.env.example`
- Modify: `README.md`
- Test: `backends/python/api/tests/`

- [ ] **Step 1: Write failing tests for telemetry bootstrap and safe no-op behavior**

Cover:
- OTel bootstrap does not crash when exporter env vars are absent;
- request/error paths can emit telemetry when enabled;
- telemetry can be disabled cleanly.

- [ ] **Step 2: Implement OpenTelemetry bootstrap**

Requirements:
- use OpenTelemetry exporter env vars;
- instrument Django requests and Python logging;
- expose service name/environment labels suitable for Grafana dashboards;
- do not hard-fail application startup if collector is unavailable.

- [ ] **Step 3: Add portal-level debug controls**

Requirements:
- debug must be enableable per portal, not globally only;
- debug mode must increase diagnostic detail without exposing secrets;
- debug output should flow through telemetry/support channels, not depend on local filesystem logs.

- [ ] **Step 4: Verify telemetry wiring**

Run:

```bash
docker compose --env-file .env run --rm api-python python manage.py check
docker compose --env-file .env run --rm api-python python manage.py test
```

Expected: app remains stable with and without OTel env vars.

- [ ] **Step 5: Commit**

```bash
git add backends/python/api/otel.py backends/python/api/asgi.py backends/python/api/wsgi.py backends/python/api/config.py backends/python/api/main/utils/decorators/log_errors.py .env.example README.md
git commit -m "feat: add opentelemetry runtime and portal debug controls"
```

## Chunk 5: Automated Error Tickets Through Internal Proxy

### Task 5: Forward support-grade failures through `mptools` proxy

**Files:**
- Create: `backends/python/api/error_reporting.py`
- Modify: `backends/python/api/config.py`
- Modify: `backends/python/api/main/utils/decorators/log_errors.py`
- Modify: `README.md`
- Test: `backends/python/api/tests/`

- [ ] **Step 1: Add failing tests for support proxy reporting**

Cover:
- fatal handler errors are reported through a single internal endpoint;
- internal proxy URL comes from env;
- reporting failures never break the user-facing response path.

- [ ] **Step 2: Implement error reporting proxy integration**

Requirements:
- send structured error payloads to internal `mptools` proxy only;
- never expose the underlying internal service topology to the client;
- include portal identifiers, request context, trace/span IDs when available;
- redact tokens, secrets, raw auth payloads, and sensitive file contents.

- [ ] **Step 3: Define support payload contract**

Document minimum payload fields:
- service name;
- environment;
- portal/member/domain;
- request handler;
- error class/message;
- traceback hash/full traceback policy;
- trace ID / span ID;
- optional debug profile state.

- [ ] **Step 4: Verify safe degradation**

Run targeted tests and confirm:
- if `mptools` is down, API still returns the original JSON error response;
- telemetry and support reporting can coexist.

- [ ] **Step 5: Commit**

```bash
git add backends/python/api/error_reporting.py backends/python/api/config.py backends/python/api/main/utils/decorators/log_errors.py README.md
git commit -m "feat: add internal support ticket proxy for backend errors"
```

## Chunk 6: Deployment, Security, And Release Gates

### Task 6: Encode cloud deployment and release constraints

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Create: `docs/release/python-prod-checklist.md`

- [ ] **Step 1: Add deployment checklist for target cloud**

Checklist must explicitly cover:
- external MySQL;
- external RabbitMQ;
- Nginx reverse proxy;
- required env vars;
- health checks;
- migration order;
- worker scaling expectations.

- [ ] **Step 2: Add release gates**

Document mandatory gates:
- Harbor image scan must have no `Critical` or `High` vulnerabilities;
- image tag must be versioned and provided to cloud admins;
- no release claim without MySQL-backed smoke verification;
- support path for post-release incidents must rely on telemetry + `mptools`, not shell log access.

- [ ] **Step 3: Add upload/runtime operational constraints**

Document:
- Nginx body size limit must match importer upload requirements;
- HTTP timeout and worker timeout budgets must be aligned;
- queue backlog should not block HTTP upload responses.

- [ ] **Step 4: Verify compose/docs consistency**

Run:

```bash
docker compose --env-file .env config
```

Expected: docs and compose definitions describe the same runtime shape.

- [ ] **Step 5: Commit**

```bash
git add README.md .env.example docker-compose.yml docs/release/python-prod-checklist.md
git commit -m "docs: add python production deployment and release gates"
```

## Notes For The Implementing Agent

- `gunicorn` is already present in `backends/python/api/requirements.txt`, but it is not a queue mechanism.
- The correct split is:
  - `Nginx -> Gunicorn -> Django` for HTTP requests and file uploads.
  - `Django -> Celery -> RabbitMQ -> Celery worker` for background importer execution.
- Production readiness is not complete until the Python path is verified against external `MySQL`, not just local postgres.
- Because cloud admins do not provide direct application logs, OTel + Grafana + `mptools` reporting are operational requirements, not optional nice-to-haves.
