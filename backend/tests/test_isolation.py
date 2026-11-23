"""Cross-tenant isolation tests: API level and database (RLS) level."""

from __future__ import annotations

import uuid

import psycopg
import pytest

from tests.conftest import APP_DSN, create_org, owner_query, register, unique_email


async def _two_tenants(client):
    a, b = await register(client, name="Alice"), await register(client, name="Bob")
    org_a, org_b = await create_org(client, a, "Alpha Foods"), await create_org(client, b, "Beta Motors")
    return a, b, org_a, org_b


@pytest.mark.parametrize("path", ["", "/members", "/workspaces", "/invitations", "/roles", "/audit-logs", "/clients"])
async def test_api_denies_foreign_tenant(client, path):
    a, _, _, org_b = await _two_tenants(client)
    r = await client.get(f"/api/v1/organizations/{org_b['id']}{path}", headers=a["headers"])
    assert r.status_code == 404, r.text


async def test_api_denies_foreign_tenant_writes(client):
    a, b, org_a, org_b = await _two_tenants(client)
    base = f"/api/v1/organizations/{org_b['id']}"
    assert (await client.patch(base, json={"name": "pwned"}, headers=a["headers"])).status_code == 404
    assert (await client.post(f"{base}/workspaces", json={"name": "pwned"}, headers=a["headers"])).status_code == 404
    assert (await client.post(f"{base}/members", json={"email": unique_email()},
                              headers=a["headers"])).status_code == 404
    # referencing B's membership through A's org path must not work either
    members_b = (await client.get(f"{base}/members", headers=b["headers"])).json()
    r = await client.delete(f"/api/v1/organizations/{org_a['id']}/members/{members_b[0]['membership_id']}",
                            headers=a["headers"])
    assert r.status_code == 404
    # and the org list shows only one's own
    assert [o["id"] for o in (await client.get("/api/v1/organizations", headers=a["headers"])).json()] == [org_a["id"]]


async def test_workspace_from_other_tenant_rejected_in_invitation(client):
    a, b, org_a, org_b = await _two_tenants(client)
    ws_b = (await client.get(f"/api/v1/organizations/{org_b['id']}/workspaces", headers=b["headers"])).json()[0]
    r = await client.post(f"/api/v1/organizations/{org_a['id']}/members", headers=a["headers"],
                          json={"email": unique_email(), "role_key": "member", "workspace_id": ws_b["id"]})
    assert r.status_code == 404


async def test_nonexistent_and_malformed_tenant(client):
    a = await register(client)
    assert (await client.get(f"/api/v1/organizations/{uuid.uuid4()}", headers=a["headers"])).status_code == 404
    assert (await client.get("/api/v1/organizations/not-a-uuid", headers=a["headers"])).status_code == 422


# --- database level ---------------------------------------------------------------------------------------


def _app_conn():
    return psycopg.connect(APP_DSN)


async def test_app_role_cannot_bypass_rls():
    with _app_conn() as conn:
        row = conn.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user").fetchone()
        assert row == (False, False)
        owners = conn.execute(
            "SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner = current_user").fetchone()
        assert owners == (0,)
        forced = conn.execute(
            "SELECT relname FROM pg_class WHERE relname = ANY(%s) AND NOT (relrowsecurity AND relforcerowsecurity)",
            (["tenants", "workspaces", "tenant_users", "user_roles", "invitations", "roles", "role_permissions",
              "audit_logs"],)).fetchall()
        assert forced == []


async def test_rls_returns_nothing_without_context(client):
    await _two_tenants(client)
    with _app_conn() as conn:
        for table in ["tenants", "workspaces", "tenant_users", "user_roles", "invitations", "audit_logs"]:
            (n,) = conn.execute(f"SELECT count(*) FROM {table}").fetchone()  # noqa: S608
            assert n == 0, f"{table} leaked {n} rows without tenant context"


async def test_rls_scopes_reads_and_blocks_cross_tenant_writes(client):
    _, _, org_a, org_b = await _two_tenants(client)
    with _app_conn() as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (org_a["id"],))
        ids = {r[0] for r in conn.execute("SELECT tenant_id::text FROM workspaces")}
        assert ids == {org_a["id"]}
        # update/delete of another tenant's rows silently affects nothing
        cur = conn.execute("UPDATE workspaces SET name = 'pwned' WHERE tenant_id = %s", (org_b["id"],))
        assert cur.rowcount == 0
        cur = conn.execute("UPDATE tenants SET name = 'pwned' WHERE id = %s", (org_b["id"],))
        assert cur.rowcount == 0
        # inserting into another tenant violates the policy
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("INSERT INTO workspaces (id, tenant_id, name, slug) VALUES (gen_random_uuid(), %s, 'x', 'x')",
                         (org_b["id"],))
        conn.rollback()


async def test_audit_log_is_append_only(client):
    _, _, org_a, _ = await _two_tenants(client)
    with _app_conn() as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (org_a["id"],))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE audit_logs SET action = 'tampered'")
        conn.rollback()
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (org_a["id"],))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM audit_logs")
        conn.rollback()


async def test_system_roles_cannot_be_modified_by_app():
    with _app_conn() as conn:
        cur = conn.execute("UPDATE roles SET name = 'pwned' WHERE key = 'owner'")
        assert cur.rowcount == 0
        cur = conn.execute("DELETE FROM role_permissions WHERE tenant_id IS NULL")
        assert cur.rowcount == 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("INSERT INTO permissions (id, code, module, description) "
                         "VALUES (gen_random_uuid(), 'x.y', 'x', 'x')")


# --- Phase 2 brand tables ----------------------------------------------------------------------------


async def make_brand(client, user, org, name="Acme Dental"):
    from tests.test_brand import make_brand as mk

    return await mk(client, user, org, name)


async def test_rls_blocks_brand_rows_without_context(client):
    u = await register(client)
    org = await create_org(client, u)
    await make_brand(client, u, org)
    other = await create_org(client, u, "Other org")
    with psycopg.connect(APP_DSN) as conn:
        for table in ("brand_profiles", "products", "brand_guidelines", "brand_assets"):
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0  # noqa: S608
        conn.execute("SELECT set_config('app.tenant_id', %s, true)", (other["id"],))
        assert conn.execute("SELECT count(*) FROM brand_profiles").fetchone()[0] == 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("INSERT INTO brand_profiles (id, tenant_id, name, slug) VALUES (%s, %s, 'x', 'x')",
                         (uuid.uuid4(), org["id"]))
        conn.rollback()
        conn.execute("SELECT set_config('app.tenant_id', %s, true)", (org["id"],))
        assert conn.execute("SELECT count(*) FROM brand_profiles").fetchone()[0] == 1


async def test_composite_fk_blocks_cross_tenant_reference(client):
    """Even the owner role (bypassing RLS) cannot attach a product to another tenant's brand."""
    a, b = await register(client), await register(client)
    org_a, org_b = await create_org(client, a), await create_org(client, b)
    brand_b = await make_brand(client, b, org_b)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        owner_query("INSERT INTO products (id, tenant_id, brand_id, name) VALUES (%s, %s, %s, 'x')",
                    uuid.uuid4(), org_a["id"], brand_b["id"])
