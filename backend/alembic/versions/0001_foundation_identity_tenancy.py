"""Phase 1 foundation: identity, tenancy, RBAC, audit log, outbox, RLS.

Revision ID: 0001_foundation
Revises:
Create Date: 2026-11-22
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.core.config import get_settings
from app.modules.tenant.permissions.catalog import sync_catalog_sql

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None

TS = "created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()"

TENANT_RLS_TABLES = ["workspaces", "user_roles", "invitations"]


def upgrade() -> None:
    app_role = get_settings().app_db_role
    ex = op.execute

    ex("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # --- RLS context helpers --------------------------------------------------------------------------------
    ex("""
    CREATE FUNCTION app_current_tenant() RETURNS uuid LANGUAGE sql STABLE AS
    $$ SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid $$;
    CREATE FUNCTION app_current_user() RETURNS uuid LANGUAGE sql STABLE AS
    $$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$;
    CREATE FUNCTION set_updated_at() RETURNS trigger LANGUAGE plpgsql AS
    $$ BEGIN NEW.updated_at = now(); RETURN NEW; END $$;
    """)

    # --- identity ------------------------------------------------------------------------------------------
    ex(f"""
    CREATE TABLE users (
      id uuid PRIMARY KEY,
      email varchar(320) NOT NULL,
      password_hash text,
      full_name varchar(200) NOT NULL,
      status varchar(20) NOT NULL DEFAULT 'active',
      email_verified_at timestamptz,
      mfa_enabled boolean NOT NULL DEFAULT false,
      mfa_secret_encrypted bytea,
      is_platform_admin boolean NOT NULL DEFAULT false,
      failed_login_count integer NOT NULL DEFAULT 0,
      locked_until timestamptz,
      last_login_at timestamptz,
      password_changed_at timestamptz,
      deleted_at timestamptz,
      {TS},
      CONSTRAINT uq_users_email UNIQUE (email),
      CONSTRAINT ck_users_email_lower CHECK (email = lower(email)),
      CONSTRAINT ck_users_status CHECK (status IN ('active', 'disabled')),
      CONSTRAINT ck_users_mfa_secret CHECK (NOT mfa_enabled OR mfa_secret_encrypted IS NOT NULL)
    );

    CREATE TABLE sessions (
      id uuid PRIMARY KEY,
      user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      refresh_token_hash varchar(64) NOT NULL,
      previous_token_hash varchar(64),
      user_agent varchar(500),
      ip_address varchar(64),
      last_used_at timestamptz NOT NULL DEFAULT now(),
      expires_at timestamptz NOT NULL,
      revoked_at timestamptz,
      revoked_reason varchar(50),
      {TS},
      CONSTRAINT uq_sessions_refresh_token_hash UNIQUE (refresh_token_hash)
    );
    CREATE INDEX ix_sessions_user_id ON sessions (user_id) WHERE revoked_at IS NULL;

    CREATE TABLE auth_tokens (
      id uuid PRIMARY KEY,
      user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      purpose varchar(30) NOT NULL,
      token_hash varchar(64) NOT NULL,
      expires_at timestamptz NOT NULL,
      consumed_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT uq_auth_tokens_token_hash UNIQUE (token_hash),
      CONSTRAINT ck_auth_tokens_purpose CHECK (purpose IN ('email_verification', 'password_reset', 'mfa_challenge'))
    );
    CREATE INDEX ix_auth_tokens_user_purpose ON auth_tokens (user_id, purpose);

    CREATE TABLE mfa_recovery_codes (
      id uuid PRIMARY KEY,
      user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      code_hash varchar(64) NOT NULL,
      used_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_mfa_recovery_codes_user_id ON mfa_recovery_codes (user_id);
    """)

    # --- tenancy -------------------------------------------------------------------------------------------
    ex(f"""
    CREATE TABLE tenants (
      id uuid PRIMARY KEY,
      name varchar(200) NOT NULL,
      slug varchar(80) NOT NULL,
      tenant_type varchar(20) NOT NULL,
      parent_tenant_id uuid REFERENCES tenants(id),
      status varchar(20) NOT NULL DEFAULT 'active',
      industry varchar(100),
      website varchar(500),
      country_code char(2),
      timezone varchar(64) NOT NULL DEFAULT 'UTC',
      default_currency char(3) NOT NULL DEFAULT 'USD',
      created_by uuid REFERENCES users(id),
      deleted_at timestamptz,
      {TS},
      CONSTRAINT uq_tenants_slug UNIQUE (slug),
      CONSTRAINT ck_tenants_type CHECK (tenant_type IN ('business', 'agency', 'client', 'enterprise')),
      CONSTRAINT ck_tenants_status CHECK (status IN ('active', 'suspended', 'closed')),
      CONSTRAINT ck_tenants_client_parent CHECK ((tenant_type = 'client') = (parent_tenant_id IS NOT NULL)),
      CONSTRAINT ck_tenants_slug_format CHECK (slug ~ '^[a-z0-9]([a-z0-9-]*[a-z0-9])?$')
    );
    CREATE INDEX ix_tenants_parent_tenant_id ON tenants (parent_tenant_id) WHERE parent_tenant_id IS NOT NULL;

    CREATE TABLE workspaces (
      id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      name varchar(200) NOT NULL,
      slug varchar(80) NOT NULL,
      description text,
      is_default boolean NOT NULL DEFAULT false,
      status varchar(20) NOT NULL DEFAULT 'active',
      deleted_at timestamptz,
      {TS},
      CONSTRAINT uq_workspaces_id_tenant UNIQUE (id, tenant_id),
      CONSTRAINT uq_workspaces_tenant_slug UNIQUE (tenant_id, slug),
      CONSTRAINT ck_workspaces_status CHECK (status IN ('active', 'archived'))
    );
    CREATE UNIQUE INDEX uq_workspaces_one_default ON workspaces (tenant_id) WHERE is_default;

    CREATE TABLE permissions (
      id uuid PRIMARY KEY,
      code varchar(100) NOT NULL,
      module varchar(50) NOT NULL,
      scope varchar(20) NOT NULL DEFAULT 'tenant',
      description varchar(300) NOT NULL,
      CONSTRAINT uq_permissions_code UNIQUE (code),
      CONSTRAINT ck_permissions_scope CHECK (scope IN ('tenant', 'platform'))
    );

    CREATE TABLE roles (
      id uuid PRIMARY KEY,
      tenant_id uuid REFERENCES tenants(id),
      key varchar(50) NOT NULL,
      name varchar(100) NOT NULL,
      description varchar(300),
      is_system boolean NOT NULL DEFAULT false,
      {TS},
      CONSTRAINT uq_roles_tenant_key UNIQUE NULLS NOT DISTINCT (tenant_id, key),
      CONSTRAINT ck_roles_system_scope CHECK (is_system = (tenant_id IS NULL)),
      CONSTRAINT ck_roles_key_format CHECK (key ~ '^[a-z][a-z0-9_]*$')
    );

    CREATE TABLE role_permissions (
      role_id uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
      permission_id uuid NOT NULL REFERENCES permissions(id),
      tenant_id uuid REFERENCES tenants(id),
      PRIMARY KEY (role_id, permission_id)
    );
    CREATE INDEX ix_role_permissions_tenant_id ON role_permissions (tenant_id);

    CREATE TABLE tenant_users (
      id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      user_id uuid NOT NULL REFERENCES users(id),
      status varchar(20) NOT NULL DEFAULT 'active',
      invited_by uuid REFERENCES users(id),
      joined_at timestamptz NOT NULL DEFAULT now(),
      {TS},
      CONSTRAINT uq_tenant_users_tenant_user UNIQUE (tenant_id, user_id),
      CONSTRAINT uq_tenant_users_id_tenant_user UNIQUE (id, tenant_id, user_id),
      CONSTRAINT ck_tenant_users_status CHECK (status IN ('active', 'suspended'))
    );
    CREATE INDEX ix_tenant_users_user_id ON tenant_users (user_id);

    CREATE TABLE user_roles (
      id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      membership_id uuid NOT NULL,
      user_id uuid NOT NULL,
      role_id uuid NOT NULL REFERENCES roles(id),
      workspace_id uuid,
      created_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT fk_user_roles_membership FOREIGN KEY (membership_id, tenant_id, user_id)
        REFERENCES tenant_users (id, tenant_id, user_id) ON DELETE CASCADE,
      CONSTRAINT fk_user_roles_workspace FOREIGN KEY (workspace_id, tenant_id)
        REFERENCES workspaces (id, tenant_id) ON DELETE CASCADE,
      CONSTRAINT uq_user_roles_assignment UNIQUE NULLS NOT DISTINCT (membership_id, role_id, workspace_id)
    );
    CREATE INDEX ix_user_roles_tenant_user ON user_roles (tenant_id, user_id);

    CREATE TABLE invitations (
      id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      email varchar(320) NOT NULL,
      role_id uuid NOT NULL REFERENCES roles(id),
      workspace_id uuid,
      token_hash varchar(64) NOT NULL,
      status varchar(20) NOT NULL DEFAULT 'pending',
      invited_by uuid NOT NULL REFERENCES users(id),
      expires_at timestamptz NOT NULL,
      accepted_at timestamptz,
      accepted_by uuid REFERENCES users(id),
      {TS},
      CONSTRAINT uq_invitations_token_hash UNIQUE (token_hash),
      CONSTRAINT fk_invitations_workspace FOREIGN KEY (workspace_id, tenant_id) REFERENCES workspaces (id, tenant_id),
      CONSTRAINT ck_invitations_status CHECK (status IN ('pending', 'accepted', 'revoked', 'expired')),
      CONSTRAINT ck_invitations_email_lower CHECK (email = lower(email))
    );
    CREATE UNIQUE INDEX uq_invitations_pending_email ON invitations (tenant_id, email) WHERE status = 'pending';
    CREATE INDEX ix_invitations_tenant_created ON invitations (tenant_id, created_at DESC);
    """)

    # --- shared infrastructure -----------------------------------------------------------------------------
    ex("""
    CREATE TABLE audit_logs (
      id uuid PRIMARY KEY,
      tenant_id uuid REFERENCES tenants(id),
      actor_user_id uuid REFERENCES users(id),
      actor_type varchar(20) NOT NULL DEFAULT 'user',
      action varchar(100) NOT NULL,
      resource_type varchar(50),
      resource_id varchar(100),
      request_id varchar(64),
      ip_address varchar(64),
      user_agent varchar(500),
      metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
      occurred_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT ck_audit_logs_actor_type CHECK (actor_type IN ('user', 'system', 'agent', 'platform_admin'))
    );
    CREATE INDEX ix_audit_logs_tenant_occurred ON audit_logs (tenant_id, occurred_at DESC);
    CREATE INDEX ix_audit_logs_actor ON audit_logs (actor_user_id, occurred_at DESC);

    CREATE TABLE outbox_events (
      id uuid PRIMARY KEY,
      tenant_id uuid,
      event_type varchar(100) NOT NULL,
      payload jsonb NOT NULL,
      status varchar(20) NOT NULL DEFAULT 'pending',
      attempts integer NOT NULL DEFAULT 0,
      available_at timestamptz NOT NULL DEFAULT now(),
      last_error text,
      created_at timestamptz NOT NULL DEFAULT now(),
      processed_at timestamptz,
      CONSTRAINT ck_outbox_events_status CHECK (status IN ('pending', 'done', 'dead'))
    );
    CREATE INDEX ix_outbox_events_due ON outbox_events (available_at) WHERE status = 'pending';
    """)

    for table in ["users", "sessions", "tenants", "workspaces", "roles", "tenant_users", "invitations"]:
        ex(f"CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table} "
           f"FOR EACH ROW EXECUTE FUNCTION set_updated_at()")

    # --- Seed permission catalog and system roles (before RLS is forced) -----------------------------------------------------
    bind = op.get_bind()
    for sql, params in sync_catalog_sql():
        bind.execute(sa.text(sql), params)

    # --- Row-level security --------------------------------------------------------------------------------
    for table in ["tenants", "tenant_users", "roles", "role_permissions", "audit_logs", *TENANT_RLS_TABLES]:
        ex(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY; ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")

    for table in TENANT_RLS_TABLES:
        ex(f"""CREATE POLICY tenant_isolation ON {table}
               USING (tenant_id = app_current_tenant()) WITH CHECK (tenant_id = app_current_tenant())""")

    ex("""
    -- A user always sees their own memberships (to list organizations); otherwise only the active tenant's.
    CREATE POLICY tenant_users_select ON tenant_users FOR SELECT
      USING (tenant_id = app_current_tenant() OR user_id = app_current_user());
    CREATE POLICY tenant_users_write ON tenant_users FOR ALL
      USING (tenant_id = app_current_tenant()) WITH CHECK (tenant_id = app_current_tenant());

    -- Tenants: the active tenant, tenants the user belongs to, and clients of agencies the user belongs to.
    CREATE POLICY tenants_select ON tenants FOR SELECT USING (
      id = app_current_tenant()
      OR id IN (SELECT tenant_id FROM tenant_users WHERE user_id = app_current_user() AND status = 'active')
      OR parent_tenant_id IN (SELECT tenant_id FROM tenant_users
                              WHERE user_id = app_current_user() AND status = 'active')
    );
    CREATE POLICY tenants_insert ON tenants FOR INSERT WITH CHECK (id = app_current_tenant());
    CREATE POLICY tenants_update ON tenants FOR UPDATE
      USING (id = app_current_tenant()) WITH CHECK (id = app_current_tenant());

    -- Roles: system roles (tenant_id NULL) are readable by all; custom roles only inside their tenant.
    CREATE POLICY roles_select ON roles FOR SELECT
      USING (tenant_id IS NULL OR tenant_id = app_current_tenant());
    CREATE POLICY roles_insert ON roles FOR INSERT WITH CHECK (tenant_id = app_current_tenant());
    CREATE POLICY roles_update ON roles FOR UPDATE
      USING (tenant_id = app_current_tenant()) WITH CHECK (tenant_id = app_current_tenant());
    CREATE POLICY roles_delete ON roles FOR DELETE USING (tenant_id = app_current_tenant());

    CREATE POLICY role_permissions_select ON role_permissions FOR SELECT
      USING (tenant_id IS NULL OR tenant_id = app_current_tenant());
    CREATE POLICY role_permissions_insert ON role_permissions FOR INSERT WITH CHECK (tenant_id = app_current_tenant());
    CREATE POLICY role_permissions_delete ON role_permissions FOR DELETE USING (tenant_id = app_current_tenant());

    -- Audit: tenant events in the active tenant; personal (tenant-less) security events for their actor.
    CREATE POLICY audit_logs_select ON audit_logs FOR SELECT USING (
      tenant_id = app_current_tenant() OR (tenant_id IS NULL AND actor_user_id = app_current_user()));
    CREATE POLICY audit_logs_insert ON audit_logs FOR INSERT WITH CHECK (
      tenant_id = app_current_tenant() OR tenant_id IS NULL);
    """)

    # --- Grants for the runtime role (not owner, NOBYPASSRLS) ---------------------------------------------
    ex(f"""
    GRANT USAGE ON SCHEMA public TO {app_role};
    GRANT SELECT, INSERT, UPDATE, DELETE ON users, sessions, auth_tokens, mfa_recovery_codes TO {app_role};
    GRANT SELECT, INSERT, UPDATE ON tenants TO {app_role};
    GRANT SELECT, INSERT, UPDATE, DELETE ON workspaces, roles, role_permissions, tenant_users, user_roles,
      invitations TO {app_role};
    GRANT SELECT ON permissions TO {app_role};
    GRANT SELECT, INSERT ON audit_logs TO {app_role};
    GRANT SELECT, INSERT, UPDATE ON outbox_events TO {app_role};
    GRANT EXECUTE ON FUNCTION app_current_tenant(), app_current_user() TO {app_role};
    """)



def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS outbox_events, audit_logs, invitations, user_roles, tenant_users, role_permissions,
      roles, permissions, workspaces, tenants, mfa_recovery_codes, auth_tokens, sessions, users CASCADE;
    DROP FUNCTION IF EXISTS app_current_tenant(), app_current_user(), set_updated_at();
    """)
