#!/bin/bash
# Creates the schema-owner and runtime roles on first container start.
# Runtime role: NOSUPERUSER NOBYPASSRLS and not the table owner, so RLS always applies to it.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE ROLE xploads_owner LOGIN PASSWORD '${XPLOADS_OWNER_PASSWORD}' NOSUPERUSER NOCREATEROLE BYPASSRLS;
CREATE ROLE xploads_app   LOGIN PASSWORD '${XPLOADS_APP_PASSWORD}'   NOSUPERUSER NOCREATEROLE NOBYPASSRLS;
GRANT ALL ON DATABASE ${POSTGRES_DB} TO xploads_owner;
GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO xploads_app;
ALTER SCHEMA public OWNER TO xploads_owner;
SQL
