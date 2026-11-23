# database/

The authoritative schema lives in Alembic migrations under `backend/alembic/versions/` (one linear history, revision
files prefixed by module). This keeps migrations next to the models they describe and runnable from the backend image.

- `seeds/` — idempotent seed data. The permission catalog and system roles are seeded by migration `0001` and can be
  re-applied with `python -m app.cli sync-permissions`.
- `migrations/` — reserved for raw SQL operational scripts (e.g. one-off data fixes) that are not part of Alembic.

Design documentation: `docs/database/SCHEMA.md`.
