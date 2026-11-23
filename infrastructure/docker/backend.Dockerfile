# API and Celery workers share one image; the command differs per service.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

FROM base AS deps
COPY backend/requirements/base.txt requirements/base.txt
RUN pip install -r requirements/base.txt

FROM deps AS runtime
# FFmpeg is added in Phase 4 for creative rendering workers.
RUN useradd --create-home --uid 10001 xploads
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app
USER xploads
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3).status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--workers", "2"]

FROM deps AS test
COPY backend/requirements/dev.txt requirements/dev.txt
RUN pip install -r requirements/dev.txt
COPY backend ./
CMD ["pytest", "-q"]
