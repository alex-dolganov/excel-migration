
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

Sample Nginx config for the Python app:

- [infrastructure/nginx/python-app.conf](./infrastructure/nginx/python-app.conf)

Release checklist:

- [docs/release/python-prod-checklist.md](./docs/release/python-prod-checklist.md)
