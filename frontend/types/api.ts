// Mirrors backend Pydantic response schemas (app/modules/*/schemas).

export interface ApiErrorBody {
  error: { code: string; message: string; request_id: string | null; details: unknown };
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  mfa_required: false;
}

export interface MfaChallengeResponse {
  mfa_required: true;
  mfa_token: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  email_verified: boolean;
  mfa_enabled: boolean;
  is_platform_admin: boolean;
  created_at: string;
}

export type TenantType = "business" | "agency" | "client" | "enterprise";

export interface Organization {
  id: string;
  name: string;
  slug: string;
  tenant_type: TenantType;
  parent_tenant_id: string | null;
  status: string;
  industry: string | null;
  website: string | null;
  country_code: string | null;
  timezone: string;
  default_currency: string;
  created_at: string;
}

export interface OrganizationAccess extends Organization {
  access: "member" | "agency";
  roles: string[];
  permissions: string[];
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  is_default: boolean;
  status: "active" | "archived";
  created_at: string;
}

export interface RoleAssignment {
  role_key: string;
  workspace_id: string | null;
}

export interface Member {
  membership_id: string;
  user_id: string;
  email: string;
  full_name: string;
  status: string;
  joined_at: string;
  roles: RoleAssignment[];
}

export interface Invitation {
  id: string;
  email: string;
  role_key: string;
  workspace_id: string | null;
  status: "pending" | "accepted" | "revoked" | "expired";
  expires_at: string;
  created_at: string;
}

export interface InvitationPreview {
  organization_name: string;
  email: string;
  role_name: string;
  inviter_name: string | null;
  expires_at: string;
}

export interface Role {
  id: string;
  key: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permissions: string[];
}

export interface AuditLog {
  id: string;
  actor_user_id: string | null;
  actor_type: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  ip_address: string | null;
  metadata: Record<string, unknown>;
  occurred_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface SessionInfo {
  id: string;
  user_agent: string | null;
  ip_address: string | null;
  created_at: string;
  last_used_at: string;
  expires_at: string;
  current: boolean;
}
