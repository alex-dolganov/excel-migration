# Python Production Readiness Checklist

## Runtime

- [ ] Production DB is external `MySQL`.
- [ ] Background jobs use external `RabbitMQ`.
- [ ] HTTP traffic goes through `Nginx -> Gunicorn -> Django`.
- [ ] Long-running importer jobs go through `Django -> Celery -> RabbitMQ -> Celery worker`.
- [ ] `DJANGO_DEBUG=false` in production.
- [ ] OpenTelemetry export is configured through standard OTLP variables.

## MySQL Smoke-Check

- [ ] Run a MySQL-backed smoke-check before release.

Example local smoke command:

```bash
COMPOSE_PROFILES=python,python-queue,queue,db-mysql BUILD_TARGET=production docker-compose --env-file .env up --build -d
docker-compose --env-file .env run --rm api-python python manage.py check
docker-compose --env-file .env run --rm api-python python manage.py test tests.test_python_prod_contract -v 2
```

## Uploads And Timeouts

- [ ] Nginx config is rendered from `infrastructure/nginx/python-app.conf.template`.
- [ ] `client_max_body_size` comes from `NGINX_CLIENT_MAX_BODY_SIZE` or is derived from `IMPORT_MAX_FILE_SIZE_BYTES`.
- [ ] Nginx `proxy_read_timeout` and `proxy_send_timeout` are at least `600s`.
- [ ] Gunicorn timeout is aligned with importer runtime expectations.
- [ ] Queue backlog does not block HTTP upload response handling.

## Observability And Support

- [ ] Direct application log access is not required for incident handling.
- [ ] Support flow relies on telemetry and admin-provided logs, not app-local shell access.
- [ ] Team understands that после публикации прямого доступа к логам нет и логи нужно запрашивать у администраторов.

## VibeCode Infra Readiness

- [ ] Deployment package stays compatible with future `VibeCode Infra`.
- [ ] Product entrypoint contract remains compatible with infra-managed port `3000`.
- [ ] Deployment notes do not depend on legacy support-proxy routing.
- [ ] Release docs can be handed to infra admins together with env examples and runtime dependencies.

## Deployment Handoff

- [ ] Infra/cloud admins received required environment variables for MySQL, RabbitMQ, OTLP, and Nginx-facing app URL.
- [ ] Migration order and rollback expectations are documented.
