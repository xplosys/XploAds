"""Phase 2 business & brand: organization profile fields, brand profiles, guidelines, products/services, assets.

Revision ID: 0002_business_brand
Revises: 0001_foundation
Create Date: 2026-11-23
"""

from __future__ import annotations

from alembic import op
from app.core.config import get_settings

revision = "0002_business_brand"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None

TS = "created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()"
TABLES = ["brand_profiles", "brand_guidelines", "products", "brand_assets"]


def upgrade() -> None:
    app_role = get_settings().app_db_role
    ex = op.execute

    # --- organization profile ------------------------------------------------------------------------------
    ex("""
    ALTER TABLE tenants
      ADD COLUMN description text,
      ADD COLUMN contact_email varchar(320),
      ADD COLUMN contact_phone varchar(40),
      ADD COLUMN address text;
    """)

    # --- brand tables --------------------------------------------------------------------------------------
    ex(f"""
    CREATE TABLE brand_profiles (
      id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      name varchar(200) NOT NULL,
      slug varchar(80) NOT NULL,
      tagline varchar(300),
      description text,
      industry varchar(100),
      website varchar(500),
      tone_of_voice text,
      target_audience text,
      value_propositions jsonb NOT NULL DEFAULT '[]',
      colors jsonb NOT NULL DEFAULT '[]',
      fonts jsonb NOT NULL DEFAULT '[]',
      social_links jsonb NOT NULL DEFAULT '{{}}',
      logo_asset_id uuid,
      is_default boolean NOT NULL DEFAULT false,
      status varchar(20) NOT NULL DEFAULT 'active',
      created_by uuid,
      deleted_at timestamptz,
      {TS},
      CONSTRAINT ck_brand_profiles_status CHECK (status IN ('active', 'archived')),
      CONSTRAINT ck_brand_profiles_json CHECK (jsonb_typeof(value_propositions) = 'array'
        AND jsonb_typeof(colors) = 'array' AND jsonb_typeof(fonts) = 'array'
        AND jsonb_typeof(social_links) = 'object'),
      CONSTRAINT uq_brand_profiles_tenant_id UNIQUE (tenant_id, id)
    );
    CREATE UNIQUE INDEX uq_brand_profiles_slug ON brand_profiles (tenant_id, slug) WHERE deleted_at IS NULL;
    CREATE UNIQUE INDEX uq_brand_profiles_default ON brand_profiles (tenant_id)
      WHERE is_default AND deleted_at IS NULL;

    CREATE TABLE brand_guidelines (
      id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      brand_id uuid NOT NULL,
      category varchar(20) NOT NULL,
      title varchar(200) NOT NULL,
      content text NOT NULL,
      sort_order integer NOT NULL DEFAULT 0,
      created_by uuid,
      {TS},
      CONSTRAINT ck_brand_guidelines_category
        CHECK (category IN ('voice', 'visual', 'messaging', 'do', 'dont', 'legal', 'other')),
      CONSTRAINT fk_brand_guidelines_brand FOREIGN KEY (tenant_id, brand_id)
        REFERENCES brand_profiles (tenant_id, id) ON DELETE CASCADE
    );
    CREATE INDEX ix_brand_guidelines_brand ON brand_guidelines (tenant_id, brand_id, sort_order);

    CREATE TABLE brand_assets (
      id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      brand_id uuid NOT NULL,
      kind varchar(20) NOT NULL,
      status varchar(20) NOT NULL DEFAULT 'pending',
      storage_key varchar(600) NOT NULL,
      original_filename varchar(255) NOT NULL,
      declared_mime_type varchar(100) NOT NULL,
      mime_type varchar(100),
      size_bytes bigint,
      checksum_sha256 varchar(64),
      width integer,
      height integer,
      title varchar(200),
      alt_text varchar(500),
      tags jsonb NOT NULL DEFAULT '[]',
      rights_source varchar(30) NOT NULL DEFAULT 'owned',
      rights_notes text,
      rights_expires_at timestamptz,
      rejection_reason varchar(300),
      uploaded_by uuid,
      upload_expires_at timestamptz NOT NULL,
      completed_at timestamptz,
      deleted_at timestamptz,
      {TS},
      CONSTRAINT uq_brand_assets_storage_key UNIQUE (storage_key),
      CONSTRAINT ck_brand_assets_kind CHECK (kind IN ('logo', 'image', 'video', 'document', 'font')),
      CONSTRAINT ck_brand_assets_status CHECK (status IN ('pending', 'ready', 'rejected')),
      CONSTRAINT ck_brand_assets_rights
        CHECK (rights_source IN ('owned', 'licensed', 'stock', 'user_generated', 'ai_generated')),
      CONSTRAINT ck_brand_assets_key_prefix CHECK (storage_key LIKE 'tenants/' || tenant_id::text || '/%'),
      CONSTRAINT ck_brand_assets_tags CHECK (jsonb_typeof(tags) = 'array'),
      CONSTRAINT uq_brand_assets_tenant_id UNIQUE (tenant_id, id),
      CONSTRAINT fk_brand_assets_brand FOREIGN KEY (tenant_id, brand_id) REFERENCES brand_profiles (tenant_id, id)
    );
    CREATE INDEX ix_brand_assets_brand ON brand_assets (tenant_id, brand_id, created_at DESC)
      WHERE deleted_at IS NULL;
    CREATE INDEX ix_brand_assets_pending ON brand_assets (upload_expires_at) WHERE status = 'pending';

    ALTER TABLE brand_profiles ADD CONSTRAINT fk_brand_profiles_logo
      FOREIGN KEY (tenant_id, logo_asset_id) REFERENCES brand_assets (tenant_id, id)
      ON DELETE SET NULL (logo_asset_id);

    CREATE TABLE products (
      id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      brand_id uuid NOT NULL,
      kind varchar(20) NOT NULL DEFAULT 'product',
      name varchar(200) NOT NULL,
      description text,
      sku varchar(100),
      price numeric(20, 6),
      currency char(3),
      price_unit varchar(50),
      url varchar(500),
      features jsonb NOT NULL DEFAULT '[]',
      image_asset_id uuid,
      status varchar(20) NOT NULL DEFAULT 'active',
      created_by uuid,
      deleted_at timestamptz,
      {TS},
      CONSTRAINT ck_products_kind CHECK (kind IN ('product', 'service')),
      CONSTRAINT ck_products_status CHECK (status IN ('active', 'archived')),
      CONSTRAINT ck_products_price CHECK (price IS NULL OR price >= 0),
      CONSTRAINT ck_products_currency CHECK (price IS NULL OR currency IS NOT NULL),
      CONSTRAINT ck_products_features CHECK (jsonb_typeof(features) = 'array'),
      CONSTRAINT fk_products_brand FOREIGN KEY (tenant_id, brand_id) REFERENCES brand_profiles (tenant_id, id),
      CONSTRAINT fk_products_image FOREIGN KEY (tenant_id, image_asset_id) REFERENCES brand_assets (tenant_id, id)
        ON DELETE SET NULL (image_asset_id)
    );
    CREATE INDEX ix_products_brand ON products (tenant_id, brand_id) WHERE deleted_at IS NULL;
    CREATE UNIQUE INDEX uq_products_sku ON products (tenant_id, brand_id, sku)
      WHERE sku IS NOT NULL AND deleted_at IS NULL;
    """)

    for table in TABLES:
        ex(f"CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table} "
           "FOR EACH ROW EXECUTE FUNCTION set_updated_at()")
        ex(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY; ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        ex(f"""CREATE POLICY tenant_isolation ON {table}
               USING (tenant_id = app_current_tenant()) WITH CHECK (tenant_id = app_current_tenant())""")

    # Maintenance needs to find abandoned uploads across tenants without giving the runtime role BYPASSRLS.
    # This definer function returns only what the cleanup job needs; the job then acts per tenant under RLS.
    ex("""
    CREATE FUNCTION stale_pending_assets(max_rows integer)
    RETURNS TABLE (id uuid, tenant_id uuid, storage_key varchar)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS
    $$ SELECT id, tenant_id, storage_key FROM brand_assets
       WHERE status = 'pending' AND upload_expires_at < now() - interval '1 hour'
       ORDER BY upload_expires_at LIMIT LEAST(max_rows, 500) $$;
    REVOKE ALL ON FUNCTION stale_pending_assets(integer) FROM PUBLIC;
    """)

    ex(f"""
    GRANT SELECT, INSERT, UPDATE, DELETE ON brand_profiles, brand_guidelines, products, brand_assets TO {app_role};
    GRANT EXECUTE ON FUNCTION stale_pending_assets(integer) TO {app_role};
    """)


def downgrade() -> None:
    op.execute("""
    DROP FUNCTION IF EXISTS stale_pending_assets(integer);
    ALTER TABLE IF EXISTS brand_profiles DROP CONSTRAINT IF EXISTS fk_brand_profiles_logo;
    DROP TABLE IF EXISTS products, brand_assets, brand_guidelines, brand_profiles CASCADE;
    ALTER TABLE tenants DROP COLUMN IF EXISTS description, DROP COLUMN IF EXISTS contact_email,
      DROP COLUMN IF EXISTS contact_phone, DROP COLUMN IF EXISTS address;
    """)
