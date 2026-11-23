"use client";

import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, onTokenChange, refreshAccessToken, setAccessToken } from "@/services/api-client";
import type { User } from "@/types/api";

type Status = "loading" | "authenticated" | "anonymous";

interface AuthState {
  status: Status;
  user: User | null;
  /** Store a freshly issued access token and load the user. */
  signIn: (accessToken: string) => Promise<void>;
  signOut: () => Promise<void>;
  reloadUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUser] = useState<User | null>(null);
  const qc = useQueryClient();

  const loadUser = useCallback(async () => {
    try {
      const me = await api<User>("/auth/me");
      setUser(me);
      setStatus("authenticated");
    } catch {
      setUser(null);
      setStatus("anonymous");
    }
  }, []);

  useEffect(() => {
    // Restore the session from the HttpOnly refresh cookie on first load.
    let cancelled = false;
    refreshAccessToken().then((token) => {
      if (cancelled) return;
      if (token) void loadUser();
      else setStatus("anonymous");
    });
    const off = onTokenChange((t) => {
      if (t === null) {
        setUser(null);
        setStatus("anonymous");
      }
    });
    return () => {
      cancelled = true;
      off();
    };
  }, [loadUser]);

  const signIn = useCallback(
    async (token: string) => {
      setAccessToken(token);
      await loadUser();
    },
    [loadUser],
  );

  const signOut = useCallback(async () => {
    try {
      await api("/auth/logout", { method: "POST", auth: false });
    } finally {
      setAccessToken(null);
      qc.clear();
      if (typeof window !== "undefined") window.localStorage.removeItem("xploads.activeOrg");
    }
  }, [qc]);

  const value = useMemo(
    () => ({ status, user, signIn, signOut, reloadUser: loadUser }),
    [status, user, signIn, signOut, loadUser],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
