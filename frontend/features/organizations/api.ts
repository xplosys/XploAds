"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/services/api-client";
import type {
  AuditLog,
  Invitation,
  Member,
  Organization,
  OrganizationAccess,
  Page,
  Role,
  Workspace,
} from "@/types/api";

export const orgKeys = {
  all: ["organizations"] as const,
  one: (id: string) => ["organizations", id] as const,
  part: (id: string, part: string) => ["organizations", id, part] as const,
};

export function useOrganizations(enabled = true) {
  return useQuery({ queryKey: orgKeys.all, queryFn: () => api<OrganizationAccess[]>("/organizations"), enabled });
}

export function useOrganization(id: string) {
  return useQuery({ queryKey: orgKeys.one(id), queryFn: () => api<OrganizationAccess>(`/organizations/${id}`) });
}

export function useCreateOrganization() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; tenant_type: string; industry?: string; country_code?: string;
      timezone?: string; default_currency?: string }) =>
      api<Organization>("/organizations", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKeys.all }),
  });
}

export function useUpdateOrganization(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Organization>) => api<Organization>(`/organizations/${id}`, { method: "PATCH", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKeys.all }),
  });
}

export function useClients(id: string, enabled: boolean) {
  return useQuery({
    queryKey: orgKeys.part(id, "clients"),
    queryFn: () => api<Organization[]>(`/organizations/${id}/clients`),
    enabled,
  });
}

export function useCreateClient(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; industry?: string }) =>
      api<Organization>(`/organizations/${id}/clients`, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKeys.all }),
  });
}

export function useWorkspaces(id: string) {
  return useQuery({ queryKey: orgKeys.part(id, "workspaces"), queryFn: () => api<Workspace[]>(`/organizations/${id}/workspaces`) });
}

export function useCreateWorkspace(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string }) =>
      api<Workspace>(`/organizations/${id}/workspaces`, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKeys.part(id, "workspaces") }),
  });
}

export function useUpdateWorkspace(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ workspaceId, ...body }: { workspaceId: string; status?: string; name?: string }) =>
      api<Workspace>(`/organizations/${id}/workspaces/${workspaceId}`, { method: "PATCH", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKeys.part(id, "workspaces") }),
  });
}

export function useMembers(id: string) {
  return useQuery({ queryKey: orgKeys.part(id, "members"), queryFn: () => api<Member[]>(`/organizations/${id}/members`) });
}

export function useInvitations(id: string) {
  return useQuery({ queryKey: orgKeys.part(id, "invitations"), queryFn: () => api<Invitation[]>(`/organizations/${id}/invitations`) });
}

export function useRoles(id: string) {
  return useQuery({ queryKey: orgKeys.part(id, "roles"), queryFn: () => api<Role[]>(`/organizations/${id}/roles`) });
}

export function useInvite(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; role_key: string }) =>
      api<Invitation>(`/organizations/${id}/members`, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKeys.part(id, "invitations") }),
  });
}

export function useRevokeInvitation(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (invitationId: string) => api(`/organizations/${id}/invitations/${invitationId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKeys.part(id, "invitations") }),
  });
}

export function useSetMemberRole(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ membershipId, roleKey }: { membershipId: string; roleKey: string }) =>
      api(`/organizations/${id}/members/${membershipId}/roles`, { method: "PUT", body: { roles: [{ role_key: roleKey }] } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKeys.part(id, "members") }),
  });
}

export function useRemoveMember(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (membershipId: string) => api(`/organizations/${id}/members/${membershipId}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: orgKeys.part(id, "members") });
      qc.invalidateQueries({ queryKey: orgKeys.all });
    },
  });
}

export function useAuditLogs(id: string, offset: number) {
  return useQuery({
    queryKey: [...orgKeys.part(id, "audit"), offset],
    queryFn: () => api<Page<AuditLog>>(`/organizations/${id}/audit-logs?limit=25&offset=${offset}`),
  });
}
