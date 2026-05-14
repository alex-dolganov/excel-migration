# ---------- Base stage ----------
FROM python:3.11-slim AS base

WORKDIR /var/www/api

# Install system dependencies for database clients and migrations
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
FROM base AS production
COPY api/ .
ENV DJANGO_ENV=production \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "./scripts/start-production.sh"]
