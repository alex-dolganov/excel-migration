import os
from pathlib import Path
import sys
from urllib.parse import urlparse

from config import config

if config.db_type == "mysql":
    import pymysql

    pymysql.install_as_MySQLdb()

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = config.jwt_secret
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = ["*"]  # narrowed below after VIRTUAL_HOST is parsed

VIRTUAL_HOST = config.app_base_url

if not VIRTUAL_HOST.startswith(("http://", "https://")):
    VIRTUAL_HOST = f"https://{VIRTUAL_HOST}"

if VIRTUAL_HOST:
    CSRF_TRUSTED_ORIGINS = [VIRTUAL_HOST]

    domain = urlparse(VIRTUAL_HOST).hostname
    ALLOWED_HOSTS = [domain, "localhost", "127.0.0.1", "api-python"]
else:
    CSRF_TRUSTED_ORIGINS = []
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "api-python"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "main",
    "importer",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "wsgi.application"
ASGI_APPLICATION = "asgi.application"

if "test" in sys.argv:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "test.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql" if config.db_type == "mysql" else "django.db.backends.postgresql_psycopg2",
            "NAME": config.db_name,
            "USER": config.db_user,
            "PASSWORD": config.db_password,
            "HOST": config.db_host,
            "PORT": config.db_port,
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "api/static/"
MEDIA_URL = "api/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

def _read_positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return max(1, int(default))


IMPORT_MAX_FILE_SIZE_BYTES = _read_positive_int_env("IMPORT_MAX_FILE_SIZE_BYTES", 50 * 1024 * 1024)
DATA_UPLOAD_MAX_MEMORY_SIZE = IMPORT_MAX_FILE_SIZE_BYTES
FILE_UPLOAD_MAX_MEMORY_SIZE = IMPORT_MAX_FILE_SIZE_BYTES

CORS_ALLOW_ALL_ORIGINS = True
