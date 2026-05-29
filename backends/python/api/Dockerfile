# ---------- Base stage ----------
FROM python:3.11-slim AS base

LABEL org.opencontainers.image.title="excel-migration-api" \
      org.opencontainers.image.description="Bitrix24 Excel Import API — Django/Gunicorn backend" \
      org.opencontainers.image.source="https://github.com/your-org/excel-migration-app"

WORKDIR /var/www/api

# mysql client is needed for migrate healthchecks; postgresql-client is dev-only
RUN apt-get update && apt-get install -y \
    default-mysql-client \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Development stage ----------
FROM base AS dev
# Note: Code will be mounted as volume in dev mode
# No COPY here to avoid overwriting mounted volume
ENV DJANGO_ENV=development \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "./scripts/start-dev.sh"]

# ---------- Production stage ----------
FROM python:3.11-slim AS production

LABEL org.opencontainers.image.title="excel-migration-api" \
      org.opencontainers.image.description="Bitrix24 Excel Import API — Django/Gunicorn backend" \
      org.opencontainers.image.source="https://github.com/your-org/excel-migration-app"

WORKDIR /var/www/api

# Production: only mysql client (no postgresql-client — reduces attack surface)
RUN apt-get update && apt-get install -y \
    default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ .
ENV DJANGO_ENV=production \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "./scripts/start-production.sh"]
