#!/bin/sh
set -eu

cd /var/www/api

python manage.py migrate --noinput

if [ "${DJANGO_SUPERUSER_CREATE:-0}" = "1" ] && [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  python manage.py shell <<'PY'
import os
from django.contrib.auth import get_user_model

User = get_user_model()
username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()

if username and password and not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email or "", password=password)
    print(f"Created Django superuser: {username}")
PY
fi

exec python manage.py runserver 0.0.0.0:8000
