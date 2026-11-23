# Monitoring

Phase 1 ships structured JSON logs (API, Nginx), request IDs end to end, `/health/live` and `/health/ready`
endpoints, and optional Sentry error tracking (`SENTRY_DSN`).

Prometheus metrics (`/metrics` on the API, Celery queue depth exporter) and Grafana dashboards are part of
Phase 9 and are intentionally not stubbed here, so nothing looks monitored that is not.
