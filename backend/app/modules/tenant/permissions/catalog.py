"""Permission catalog and system roles.

Permission codes are declared up front for all modules so roles stay stable as modules are implemented.
The catalog is synchronized into the database by migrations (idempotent upsert, see ``sync_catalog_sql``).
"""

from __future__ import annotations

PERMISSIONS: dict[str, tuple[str, str]] = {
    # code: (module, description)
    "organization.read": ("tenant", "View organization details"),
    "organization.update": ("tenant", "Update organization settings"),
    "organization.delete": ("tenant", "Delete or close the organization"),
    "members.read": ("tenant", "View members"),
    "members.invite": ("tenant", "Invite members"),
    "members.manage": ("tenant", "Change member roles and remove members"),
    "roles.read": ("tenant", "View roles and permissions"),
    "roles.manage": ("tenant", "Create and edit custom roles"),
    "workspaces.read": ("tenant", "View workspaces"),
    "workspaces.manage": ("tenant", "Create and edit workspaces"),
    "audit.read": ("approvals", "View audit history"),
    "agency.clients.create": ("tenant", "Create client organizations under an agency"),
    "agency.clients.access": ("tenant", "Act inside the agency's client organizations"),
    "billing.read": ("subscription", "View subscription, usage and invoices"),
    "billing.manage": ("subscription", "Change plans, buy credits, manage payment methods"),
    "providers.read": ("provider", "View AI provider settings"),
    "providers.manage": ("provider", "Configure AI providers and BYOK credentials"),
    "brands.read": ("brand", "View brand profiles and assets"),
    "brands.manage": ("brand", "Create and edit brand profiles, assets and products"),
    "creatives.read": ("creative_studio", "View creatives and the creative library"),
    "creatives.generate": ("creative_studio", "Generate AI creatives (consumes usage)"),
    "creatives.approve": ("creative_studio", "Approve or reject creatives"),
    "templates.manage": ("templates", "Create and edit templates"),
    "campaigns.read": ("campaigns", "View campaigns"),
    "campaigns.manage": ("campaigns", "Create and edit draft campaigns"),
    "campaigns.publish": ("campaigns", "Approve and publish campaigns to Meta"),
    "campaigns.budget": ("campaigns", "Approve budget changes"),
    "integrations.manage": ("meta", "Connect and disconnect Meta and WhatsApp assets"),
    "leads.read": ("crm", "View leads"),
    "leads.manage": ("crm", "Create, edit, assign and export leads"),
    "whatsapp.converse": ("whatsapp", "Read and reply to WhatsApp conversations"),
    "automation.manage": ("automation", "Create and edit workflows"),
    "analytics.read": ("analytics", "View analytics and reports"),
    "approvals.decide": ("approvals", "Decide approval requests"),
}

_ALL = set(PERMISSIONS)
_READ = {c for c in _ALL if c.endswith(".read")}

SYSTEM_ROLES: dict[str, tuple[str, str, set[str]]] = {
    "owner": ("Owner", "Full control of the organization", _ALL),
    "admin": ("Administrator", "Manage everything except deleting the organization", _ALL - {"organization.delete"}),
    "manager": (
        "Marketing manager",
        "Run brands, creatives, campaigns and leads",
        _READ
        | {
            "brands.manage", "creatives.generate", "creatives.approve", "templates.manage", "campaigns.manage",
            "campaigns.publish", "campaigns.budget", "leads.manage", "whatsapp.converse", "automation.manage",
            "approvals.decide", "agency.clients.access",
        },
    ),
    "member": (
        "Member",
        "Create drafts and work leads; cannot publish or change budgets",
        _READ - {"audit.read", "billing.read"}
        | {"brands.manage", "creatives.generate", "campaigns.manage", "leads.manage", "whatsapp.converse"},
    ),
    "sales": (
        "Sales",
        "Lead follow-up and pipeline",
        {"organization.read", "leads.read", "leads.manage", "whatsapp.converse", "analytics.read"},
    ),
    "viewer": ("Viewer", "Read-only access", _READ - {"audit.read", "billing.read"}),
    "billing_admin": ("Billing admin", "Manage billing and view usage", {"organization.read", "billing.read",
                                                                          "billing.manage", "analytics.read"}),
}

# Permissions that only make sense in the agency tenant itself and never flow into client tenants.
AGENCY_ONLY = {"agency.clients.create", "agency.clients.access"}


def sync_catalog_sql() -> list[tuple[str, dict]]:
    """Statements that upsert the catalog. Safe to run repeatedly."""
    stmts: list[tuple[str, dict]] = []
    for code, (module, desc) in PERMISSIONS.items():
        stmts.append((
            "INSERT INTO permissions (id, code, module, scope, description) "
            "VALUES (gen_random_uuid(), :code, :module, 'tenant', :desc) "
            "ON CONFLICT (code) DO UPDATE SET module = EXCLUDED.module, description = EXCLUDED.description",
            {"code": code, "module": module, "desc": desc},
        ))
    for key, (name, desc, perms) in SYSTEM_ROLES.items():
        stmts.append((
            "INSERT INTO roles (id, tenant_id, key, name, description, is_system) "
            "VALUES (gen_random_uuid(), NULL, :key, :name, :desc, true) "
            "ON CONFLICT (tenant_id, key) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description",
            {"key": key, "name": name, "desc": desc},
        ))
        stmts.append((
            "DELETE FROM role_permissions rp USING roles r, permissions p "
            "WHERE rp.role_id = r.id AND rp.permission_id = p.id AND r.tenant_id IS NULL AND r.key = :key "
            "AND NOT (p.code = ANY(:codes))",
            {"key": key, "codes": sorted(perms)},
        ))
        stmts.append((
            "INSERT INTO role_permissions (role_id, permission_id, tenant_id) "
            "SELECT r.id, p.id, NULL FROM roles r, permissions p "
            "WHERE r.tenant_id IS NULL AND r.key = :key AND p.code = ANY(:codes) "
            "ON CONFLICT DO NOTHING",
            {"key": key, "codes": sorted(perms)},
        ))
    return stmts
