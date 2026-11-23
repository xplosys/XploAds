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
  description?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  address?: string | null;
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

// --- brand kit (Phase 2) ------------------------------------------------------------------------------------

export type ColorUsage = "primary" | "secondary" | "accent" | "neutral" | "background" | "text";
export interface BrandColor { name: string; hex: string; usage: ColorUsage }
export interface BrandFont { family: string; usage: "heading" | "body" | "accent"; weight?: string | null }
export const SOCIAL_PLATFORMS = ["facebook", "instagram", "linkedin", "x", "youtube", "tiktok", "whatsapp", "website"] as const;
export type SocialPlatform = (typeof SOCIAL_PLATFORMS)[number];

export interface BrandSummary {
  id: string;
  name: string;
  slug: string;
  tagline: string | null;
  industry: string | null;
  status: "active" | "archived";
  is_default: boolean;
  logo_asset_id: string | null;
  logo_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface Brand extends BrandSummary {
  description: string | null;
  website: string | null;
  tone_of_voice: string | null;
  target_audience: string | null;
  value_propositions: string[];
  colors: BrandColor[];
  fonts: BrandFont[];
  social_links: Partial<Record<SocialPlatform, string>>;
  counts: { guidelines?: number; products?: number; assets?: number };
}

export const GUIDELINE_CATEGORIES = ["voice", "visual", "messaging", "do", "dont", "legal", "other"] as const;
export type GuidelineCategory = (typeof GUIDELINE_CATEGORIES)[number];
export interface Guideline {
  id: string;
  brand_id: string;
  category: GuidelineCategory;
  title: string;
  content: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface Product {
  id: string;
  brand_id: string;
  kind: "product" | "service";
  name: string;
  description: string | null;
  sku: string | null;
  price: string | null;
  currency: string | null;
  price_unit: string | null;
  url: string | null;
  features: string[];
  image_asset_id: string | null;
  image_url: string | null;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
}

export type AssetKind = "logo" | "image" | "video" | "document" | "font";
export type RightsSource = "owned" | "licensed" | "stock" | "user_generated" | "ai_generated";
export interface Asset {
  id: string;
  brand_id: string;
  kind: AssetKind;
  status: "pending" | "ready" | "rejected";
  original_filename: string;
  mime_type: string | null;
  size_bytes: number | null;
  checksum_sha256: string | null;
  width: number | null;
  height: number | null;
  title: string | null;
  alt_text: string | null;
  tags: string[];
  rights_source: RightsSource;
  rights_notes: string | null;
  rights_expires_at: string | null;
  rejection_reason: string | null;
  url: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface AssetRule { kind: AssetKind; mime_types: string[]; extensions: string[]; max_bytes: number }
export interface UploadTarget { url: string; method: string; fields: Record<string, string>; expires_in: number }
