"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Spinner } from "@/components/ui/misc";
import { useAuth } from "@/features/auth/auth-provider";

/** Client-side guard. Authorization is always enforced again by the API. */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (status === "anonymous") {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      router.replace(`/login?next=${next}`);
    }
  }, [status, router]);
  if (status !== "authenticated") return <Spinner label="Checking your session" />;
  return <>{children}</>;
}

export function RedirectIfAuthenticated({ children, to = "/app" }: { children: React.ReactNode; to?: string }) {
  const { status } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (status === "authenticated") router.replace(to);
  }, [status, router, to]);
  if (status === "loading") return <Spinner />;
  if (status === "authenticated") return <Spinner label="Redirecting" />;
  return <>{children}</>;
}

export function safeNext(next: string | null, fallback = "/app") {
  // Only allow same-origin relative paths to prevent open redirects.
  return next && next.startsWith("/") && !next.startsWith("//") ? next : fallback;
}
