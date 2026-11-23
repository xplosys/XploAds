"""Test harness: runs against a real PostgreSQL (RLS cannot be tested with SQLite) and Redis.

Environment (defaults suit the docker-compose stack and CI):
  TEST_PG_ADMIN_URL   superuser DSN used to create roles and the test database
  TEST_PG_HOST/PORT   where the test database lives
"""

from __future__ import annotations

import os
import tempfile
import uuid

import psycopg
import pytest

PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
PG_PORT = os.environ.get("TEST_PG_PORT", "5432")
ADMIN_URL = os.environ.get("TEST_PG_ADMIN_URL", f"postgresql://postgres@{PG_HOST}:{PG_PORT}/postgres")
TEST_DB = "xploads_test"

os.environ.update({
    "ENVIRONMENT": "test",
    "DATABASE_URL": f"postgresql+asyncpg://xploads_app:xploads_app@{PG_HOST}:{PG_PORT}/{TEST_DB}",
    "MIGRATION_DATABASE_URL": f"postgresql+psycopg://xploads_owner:xploads_owner@{PG_HOST}:{PG_PORT}/{TEST_DB}",
    "REDIS_URL": os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15"),
    "RATE_LIMIT_ENABLED": "false",
    "EMAIL_MODE": "console",
    "JWT_SECRET": "test-secret-test-secret-test-secret-1234",
    "FRONTEND_URL": "http://app.test",
    "STORAGE_BACKEND": "local",
    "STORAGE_LOCAL_PATH": os.path.join(tempfile.gettempdir(), f"xploads-test-storage-{os.getpid()}"),
    "API_PUBLIC_URL": "",
})

OWNER_DSN = f"postgresql://xploads_owner:xploads_owner@{PG_HOST}:{PG_PORT}/{TEST_DB}"
APP_DSN = f"postgresql://xploads_app:xploads_app@{PG_HOST}:{PG_PORT}/{TEST_DB}"


def _bootstrap_database() -> None:
    with psycopg.connect(ADMIN_URL, autocommit=True) as conn:
        roles = {r[0] for r in conn.execute("SELECT rolname FROM pg_roles")}
        if "xploads_owner" not in roles:
            conn.execute("CREATE ROLE xploads_owner LOGIN PASSWORD 'xploads_owner' BYPASSRLS")
        if "xploads_app" not in roles:
            conn.execute("CREATE ROLE xploads_app LOGIN PASSWORD 'xploads_app' NOBYPASSRLS")
        conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        conn.execute(f"CREATE DATABASE {TEST_DB} OWNER xploads_owner")
    test_admin = ADMIN_URL.rsplit("/", 1)[0] + f"/{TEST_DB}"
    with psycopg.connect(test_admin, autocommit=True) as conn:
        conn.execute("ALTER SCHEMA public OWNER TO xploads_owner")
        conn.execute(f"GRANT CONNECT ON DATABASE {TEST_DB} TO xploads_app")

    from alembic.config import Config

    from alembic import command

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(here, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(here, "alembic"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session", autouse=True)
def database() -> None:
    _bootstrap_database()


# Ordered deletes (not TRUNCATE ... CASCADE, which would also wipe the seeded system roles).
CLEANUP = [
    "DELETE FROM outbox_events", "DELETE FROM audit_logs", "UPDATE brand_profiles SET logo_asset_id = NULL",
    "DELETE FROM products", "DELETE FROM brand_guidelines", "DELETE FROM brand_assets", "DELETE FROM brand_profiles",
    "DELETE FROM invitations", "DELETE FROM user_roles",
    "DELETE FROM tenant_users", "DELETE FROM workspaces", "DELETE FROM role_permissions WHERE tenant_id IS NOT NULL",
    "DELETE FROM roles WHERE tenant_id IS NOT NULL", "DELETE FROM tenants WHERE parent_tenant_id IS NOT NULL",
    "DELETE FROM tenants", "DELETE FROM mfa_recovery_codes", "DELETE FROM auth_tokens", "DELETE FROM sessions",
    "DELETE FROM users",
]


@pytest.fixture(autouse=True)
def clean_db(database: None) -> None:
    with psycopg.connect(OWNER_DSN, autocommit=True) as conn:
        for stmt in CLEANUP:
            conn.execute(stmt)


@pytest.fixture
async def client():
    import httpx

    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


def owner_query(sql: str, *params: object) -> list[tuple]:
    with psycopg.connect(OWNER_DSN, autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


def latest_event_token(event_type: str, email: str) -> str:
    rows = owner_query(
        "SELECT payload->>'token' FROM outbox_events WHERE event_type = %s AND payload->>'email' = %s "
        "ORDER BY created_at DESC LIMIT 1", event_type, email)
    assert rows and rows[0][0], f"no {event_type} event for {email}"
    return rows[0][0]


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


PASSWORD = "Sup3r-Secret-Pass!"


async def register(client, email: str | None = None, name: str = "Test User", verify: bool = True) -> dict:
    """Register a user (optionally verifying the email); returns {email, token, headers}."""
    email = email or unique_email()
    r = await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD, "full_name": name})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    if verify:
        vt = latest_event_token("identity.email_verification_requested", email)
        r2 = await client.post("/api/v1/auth/verify-email", json={"token": vt})
        assert r2.status_code == 200, r2.text
    return {"email": email, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


async def create_org(client, user: dict, name: str = "Acme Dental", tenant_type: str = "business") -> dict:
    r = await client.post("/api/v1/organizations", json={"name": name, "tenant_type": tenant_type},
                          headers=user["headers"])
    assert r.status_code == 201, r.text
    return r.json()
