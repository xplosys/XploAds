"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "@/services/api-client";
import type {
  Asset,
  AssetKind,
  AssetRule,
  Brand,
  BrandSummary,
  Guideline,
  Page,
  Product,
  RightsSource,
  UploadTarget,
} from "@/types/api";

// Every brand endpoint is tenant-scoped through the X-Tenant-ID header.
export const brandKeys = {
  list: (orgId: string) => ["brands", orgId] as const,
  one: (orgId: string, brandId: string) => ["brands", orgId, brandId] as const,
  part: (orgId: string, brandId: string, part: string, extra?: unknown) =>
    ["brands", orgId, brandId, part, extra ?? null] as const,
};

export function useBrands(orgId: string, includeArchived = false, enabled = true) {
  return useQuery({
    queryKey: [...brandKeys.list(orgId), includeArchived],
    queryFn: () => api<BrandSummary[]>(`/brands${includeArchived ? "?include_archived=true" : ""}`, { tenantId: orgId }),
    enabled,
  });
}

export function useBrand(orgId: string, brandId: string) {
  return useQuery({
    queryKey: brandKeys.one(orgId, brandId),
    queryFn: () => api<Brand>(`/brands/${brandId}`, { tenantId: orgId }),
    // signed logo URLs expire after a few minutes
    staleTime: 60_000,
  });
}

function useInvalidate(orgId: string) {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: brandKeys.list(orgId) });
}

export function useCreateBrand(orgId: string) {
  const invalidate = useInvalidate(orgId);
  return useMutation({
    mutationFn: (body: Partial<Brand> & { name: string }) => api<Brand>("/brands", { method: "POST", body, tenantId: orgId }),
    onSuccess: invalidate,
  });
}

export function useUpdateBrand(orgId: string, brandId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<Brand>(`/brands/${brandId}`, { method: "PATCH", body, tenantId: orgId }),
    onSuccess: (brand) => {
      qc.setQueryData(brandKeys.one(orgId, brandId), brand);
      qc.invalidateQueries({ queryKey: brandKeys.list(orgId), exact: false, refetchType: "active" });
    },
  });
}

export function useBrandAction(orgId: string) {
  const invalidate = useInvalidate(orgId);
  return useMutation({
    mutationFn: ({ brandId, action }: { brandId: string; action: "default" | "delete" }) =>
      action === "default"
        ? api(`/brands/${brandId}/default`, { method: "POST", tenantId: orgId })
        : api(`/brands/${brandId}`, { method: "DELETE", tenantId: orgId }),
    onSuccess: invalidate,
  });
}

// --- guidelines --------------------------------------------------------------------------------------------

export function useGuidelines(orgId: string, brandId: string) {
  return useQuery({
    queryKey: brandKeys.part(orgId, brandId, "guidelines"),
    queryFn: () => api<Guideline[]>(`/brands/${brandId}/guidelines`, { tenantId: orgId }),
  });
}

export function useSaveGuideline(orgId: string, brandId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: Partial<Guideline>) =>
      id
        ? api<Guideline>(`/brands/${brandId}/guidelines/${id}`, { method: "PATCH", body, tenantId: orgId })
        : api<Guideline>(`/brands/${brandId}/guidelines`, { method: "POST", body, tenantId: orgId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: brandKeys.one(orgId, brandId) }),
  });
}

export function useDeleteGuideline(orgId: string, brandId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api(`/brands/${brandId}/guidelines/${id}`, { method: "DELETE", tenantId: orgId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: brandKeys.one(orgId, brandId) }),
  });
}

// --- products & services -----------------------------------------------------------------------------------

export interface ProductFilters {
  kind?: "product" | "service";
  status?: "active" | "archived";
  q?: string;
  offset?: number;
}

export function useProducts(orgId: string, brandId: string, filters: ProductFilters) {
  const params = new URLSearchParams({ limit: "50" });
  Object.entries(filters).forEach(([k, v]) => v !== undefined && v !== "" && params.set(k, String(v)));
  return useQuery({
    queryKey: brandKeys.part(orgId, brandId, "products", filters),
    queryFn: () => api<Page<Product>>(`/brands/${brandId}/products?${params}`, { tenantId: orgId }),
    placeholderData: keepPreviousData,
  });
}

export function useSaveProduct(orgId: string, brandId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: Record<string, unknown> & { id?: string }) =>
      id
        ? api<Product>(`/products/${id}`, { method: "PATCH", body, tenantId: orgId })
        : api<Product>(`/brands/${brandId}/products`, { method: "POST", body, tenantId: orgId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: brandKeys.one(orgId, brandId) }),
  });
}

export function useDeleteProduct(orgId: string, brandId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api(`/products/${id}`, { method: "DELETE", tenantId: orgId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: brandKeys.one(orgId, brandId) }),
  });
}

// --- assets ------------------------------------------------------------------------------------------------

export function useAssetRules() {
  return useQuery({
    queryKey: ["asset-rules"],
    queryFn: () => api<AssetRule[]>("/assets/rules"),
    staleTime: Infinity,
  });
}

export function useAssets(orgId: string, brandId: string, kind?: AssetKind) {
  const params = new URLSearchParams({ limit: "120" });
  if (kind) params.set("kind", kind);
  return useQuery({
    queryKey: brandKeys.part(orgId, brandId, "assets", kind),
    queryFn: () => api<Page<Asset>>(`/brands/${brandId}/assets?${params}`, { tenantId: orgId }),
    staleTime: 60_000, // signed URLs last five minutes
  });
}

export function useUpdateAsset(orgId: string, brandId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: Partial<Asset> & { id: string }) =>
      api<Asset>(`/assets/${id}`, { method: "PATCH", body, tenantId: orgId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: brandKeys.one(orgId, brandId) }),
  });
}

export function useDeleteAsset(orgId: string, brandId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api(`/assets/${id}`, { method: "DELETE", tenantId: orgId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: brandKeys.one(orgId, brandId) }),
  });
}

export async function assetDownloadUrl(orgId: string, assetId: string) {
  return (await api<{ url: string }>(`/assets/${assetId}/download`, { tenantId: orgId })).url;
}

/** Post the file straight to storage with the signed form (no API credentials are sent). */
function postToStorage(target: UploadTarget, file: File, onProgress?: (pct: number) => void) {
  return new Promise<void>((resolve, reject) => {
    const form = new FormData();
    Object.entries(target.fields).forEach(([k, v]) => form.append(k, v));
    form.append("file", file); // must be the last field for S3
    const xhr = new XMLHttpRequest();
    xhr.open(target.method, target.url);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(new ApiError(xhr.status, "upload_failed", xhr.status === 413 || xhr.status === 400
            ? "The storage service refused the file (too large or empty)."
            : "The upload failed. Please try again."));
    xhr.onerror = () => reject(new ApiError(0, "upload_failed", "Could not reach the storage service."));
    xhr.send(form);
  });
}

export interface UploadInput {
  brandId: string;
  kind: AssetKind;
  file: File;
  title?: string;
  rightsSource?: RightsSource;
  rightsNotes?: string;
  onProgress?: (pct: number) => void;
}

export async function uploadAsset(orgId: string, input: UploadInput): Promise<Asset> {
  const started = await api<{ asset: Asset; upload: UploadTarget }>("/assets/uploads", {
    method: "POST",
    tenantId: orgId,
    body: {
      brand_id: input.brandId,
      kind: input.kind,
      filename: input.file.name,
      content_type: input.file.type || "application/octet-stream",
      size_bytes: input.file.size,
      title: input.title || undefined,
      rights_source: input.rightsSource ?? "owned",
      rights_notes: input.rightsNotes || undefined,
    },
  });
  await postToStorage(started.upload, input.file, input.onProgress);
  return api<Asset>(`/assets/${started.asset.id}/complete`, { method: "POST", tenantId: orgId });
}

export function useUploadAsset(orgId: string, brandId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: Omit<UploadInput, "brandId">) => uploadAsset(orgId, { ...input, brandId }),
    onSettled: () => qc.invalidateQueries({ queryKey: brandKeys.one(orgId, brandId) }),
  });
}

export function formatBytes(n: number | null | undefined) {
  if (!n) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
