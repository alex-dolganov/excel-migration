#!/bin/sh
set -eu

cd /var/www/api

python manage.py migrate --noinput

exec gunicorn wsgi:application \
  --bind 0.0.0.0:${PORT:-8000} \
  --workers ${GUNICORN_WORKERS:-2} \
  --timeout ${GUNICORN_TIMEOUT:-600} \
  --graceful-timeout ${GUNICORN_GRACEFUL_TIMEOUT:-60} \
  --keep-alive ${GUNICORN_KEEPALIVE:-5}
