// Typed fetch wrapper. The access token lives only in memory; the refresh token is an HttpOnly cookie
// scoped to /api/v1/auth that JavaScript cannot read.

import type { ApiErrorBody, TokenResponse } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
    public requestId?: string | null,
  ) {
    super(message);
  }
}

let accessToken: string | null = null;
let refreshInFlight: Promise<string | null> | null = null;
const listeners = new Set<(token: string | null) => void>();

export function getAccessToken() {
  return accessToken;
}

export function setAccessToken(token: string | null) {
  accessToken = token;
  listeners.forEach((l) => l(token));
}

export function onTokenChange(listener: (token: string | null) => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as ApiErrorBody;
    return new ApiError(res.status, body.error.code, body.error.message, body.error.details, body.error.request_id);
  } catch {
    return new ApiError(res.status, "http_error", res.statusText || "Request failed");
  }
}

async function doRefresh(attempt = 0): Promise<string | null> {
  const res = await fetch(`${API_BASE}/auth/refresh`, { method: "POST", credentials: "include" });
  if (res.ok) {
    const body = (await res.json()) as TokenResponse;
    setAccessToken(body.access_token);
    return body.access_token;
  }
  const err = await parseError(res);
  // Another tab rotated the token a moment ago; its new cookie is already stored, so retry once.
  if (err.code === "refresh_conflict" && attempt === 0) {
    await new Promise((r) => setTimeout(r, 300));
    return doRefresh(1);
  }
  setAccessToken(null);
  return null;
}

/** Refresh the access token. Concurrent callers share one request (rotation is single-use). */
export function refreshAccessToken(): Promise<string | null> {
  refreshInFlight ??= doRefresh().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

type Options = Omit<RequestInit, "body"> & { body?: unknown; tenantId?: string; auth?: boolean };

export async function api<T>(path: string, { body, tenantId, auth = true, headers, ...init }: Options = {}): Promise<T> {
  const send = (token: string | null) => {
    const h = new Headers(headers);
    if (body !== undefined) h.set("Content-Type", "application/json");
    if (auth && token) h.set("Authorization", `Bearer ${token}`);
    if (tenantId) h.set("X-Tenant-ID", tenantId);
    return fetch(`${API_BASE}${path}`, {
      ...init,
      headers: h,
      credentials: "include",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  };

  let res = await send(accessToken);
  if (res.status === 401 && auth) {
    const token = await refreshAccessToken();
    if (token) res = await send(token);
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function errorMessage(err: unknown, fallback = "Something went wrong. Please try again."): string {
  if (err instanceof ApiError) {
    if (err.code === "validation_error" && Array.isArray(err.details) && err.details[0]?.msg) {
      return String(err.details[0].msg).replace(/^Value error, /, "");
    }
    return err.message;
  }
  return fallback;
}
