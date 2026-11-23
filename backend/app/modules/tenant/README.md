# `tenant` module — implemented (Phase 1)

Organizations (tenants), agency clients, workspaces, memberships, invitations, roles and permissions.

| | |
|---|---|
| Owns tables | `tenants`, `workspaces`, `tenant_users`, `user_roles`, `roles`, `role_permissions`, `permissions`, `invitations` |
| API | `/api/v1/organizations[/{id}[/clients|/workspaces|/members|/invitations|/roles|/audit-logs]]`, `/api/v1/invitations/{preview,accept}`, `/api/v1/permissions` |
| Public interface | `app.modules.tenant.api.deps` — `OrgContext` (tenant from path), `CurrentTenant` (tenant from `X-Tenant-ID`); `TenantContext.require(...)` |
| Events emitted | `tenant.invitation_created` |
| Depends on | `identity` (users), `app.core`, `app.shared` |

Key rules
- Tenant context is resolved only from verified membership (or agency access) — see `services/context.py`.
- Agency clients are separate tenants (`tenant_type='client'`, `parent_tenant_id`). Agency staff need
  `agency.clients.access`; their actions inside a client are audited with `via: agency`.
- An organization always keeps at least one owner; only owners grant or remove the owner role.
- Custom roles cannot include permissions the creator does not hold; system role keys are reserved.
- Invitations are bound to the invited email; accepting proves mailbox control and marks the email verified.
