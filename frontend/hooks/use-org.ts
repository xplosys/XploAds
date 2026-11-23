"use client";

import { useParams } from "next/navigation";

import { useOrganizations } from "@/features/organizations/api";

/** Active organization from the URL, with the caller's permissions in it. */
export function useCurrentOrg() {
  const { orgId } = useParams<{ orgId: string }>();
  const orgs = useOrganizations();
  const org = orgs.data?.find((o) => o.id === orgId);
  const can = (permission: string) => !!org?.permissions.includes(permission);
  return { orgId, org, orgs, can };
}
