#!/bin/sh
set -eu

cd /var/www/api
export PYTHONPATH="${PYTHONPATH:-/var/www:/var/www/api}"

python manage.py migrate --noinput

exec celery -A api.app_celery:celery_app worker \
  --loglevel=${CELERY_LOG_LEVEL:-info} \
  --concurrency=${CELERY_CONCURRENCY:-2}
