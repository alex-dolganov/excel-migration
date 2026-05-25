
# Python Production Notes

## Runtime contract

- HTTP path: `Nginx -> Gunicorn -> Django`
- Background path: `Django -> Celery -> RabbitMQ -> Celery worker`
- `gunicorn` is not a queue transport and does not replace RabbitMQ

## Production expectations

- Use external `MySQL` for production
- Use external `RabbitMQ` for background jobs
- Keep `DJANGO_DEBUG=false`
- Align Nginx upload/body-size and proxy timeout settings with Django/Gunicorn importer limits
- Keep OpenTelemetry export vendor-neutral via standard OTLP env vars

## Local Python runtime

- Dev Docker startup now uses `backends/python/api/scripts/start-dev.sh`: it always runs `migrate`, but creates a Django superuser only when `DJANGO_SUPERUSER_CREATE=true`.
- Local unauthenticated health probe is `GET /healthz`; protected application health remains `GET /api/health`.
- OTLP export is disabled by default in local dev even if `OTEL_EXPORTER_OTLP_ENDPOINT` is filled; enable it explicitly with `OTEL_EXPORTER_OTLP_ENABLED=true`.

## Deployment target

- Future publish target: `VibeCode Infra`
- Keep the app ready for infra-managed deployment with product entry on port `3000`
- Do not hardwire support/error delivery to legacy internal proxies
- Treat current Docker/Nginx/MySQL/RabbitMQ notes as readiness contract until Infra is fully available

Sample Nginx config for the Python app:

- [infrastructure/nginx/python-app.conf](./infrastructure/nginx/python-app.conf)
- [infrastructure/nginx/python-app.conf.template](./infrastructure/nginx/python-app.conf.template)
- [infrastructure/nginx/render-python-app-conf.mjs](./infrastructure/nginx/render-python-app-conf.mjs)

Render the Nginx config from the shared importer env contract:

```bash
node infrastructure/nginx/render-python-app-conf.mjs infrastructure/nginx/python-app.conf.template infrastructure/nginx/python-app.conf
```

Release checklist:

- [docs/release/python-prod-checklist.md](./docs/release/python-prod-checklist.md)
