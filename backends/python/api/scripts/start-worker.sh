#!/bin/sh
set -eu

cd /var/www/api
export PYTHONPATH="${PYTHONPATH:-/var/www:/var/www/api}"

python manage.py migrate --noinput

# Start beat scheduler in background (periodic tasks like stuck session cleanup)
celery -A api.app_celery:celery_app beat \
  --loglevel=${CELERY_LOG_LEVEL:-info} \
  --pidfile=/tmp/celerybeat.pid \
  --schedule=/tmp/celerybeat-schedule &

exec celery -A api.app_celery:celery_app worker \
  --loglevel=${CELERY_LOG_LEVEL:-info} \
  --concurrency=${CELERY_CONCURRENCY:-2}
