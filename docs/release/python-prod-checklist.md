# Python Production Release Checklist

## Runtime

- [ ] Production DB is external `MySQL`.
- [ ] Background jobs use external `RabbitMQ`.
- [ ] HTTP traffic goes through `Nginx -> Gunicorn -> Django`.
- [ ] Long-running importer jobs go through `Django -> Celery -> RabbitMQ -> Celery worker`.
- [ ] `DJANGO_DEBUG=false` in production.

## MySQL Smoke-Check

- [ ] Run a MySQL-backed smoke-check before release.

Example local smoke command:

```bash
COMPOSE_PROFILES=python,python-queue,queue,db-mysql BUILD_TARGET=production docker-compose --env-file .env up --build -d
docker-compose --env-file .env run --rm api-python python manage.py check
docker-compose --env-file .env run --rm api-python python manage.py test tests.test_python_prod_contract -v 2
```

## Uploads And Timeouts

- [ ] Nginx `client_max_body_size` is at least `50m`.
- [ ] Nginx `proxy_read_timeout` and `proxy_send_timeout` are at least `600s`.
- [ ] Gunicorn timeout is aligned with importer runtime expectations.
- [ ] Queue backlog does not block HTTP upload response handling.

## Observability And Support

- [ ] OpenTelemetry export is configured for production.
- [ ] Direct application log access is not required for incident handling.
- [ ] Support flow relies on telemetry and internal reporting integrations.
- [ ] Team understands that после публикации прямого доступа к логам нет и логи нужно запрашивать у администраторов.

## Harbor Release Gates

- [ ] Harbor image scan completed for the exact release tag.
- [ ] There are no `Critical` vulnerabilities.
- [ ] There are no `High` vulnerabilities.
- [ ] Release tag is documented and handed off to cloud administrators.

## Deployment Handoff

- [ ] Cloud admins received the image tag.
- [ ] Cloud admins received required environment variables for MySQL, RabbitMQ, and Nginx-facing app URL.
- [ ] Migration order and rollback expectations are documented.
