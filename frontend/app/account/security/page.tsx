"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FormError } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Badge, Spinner } from "@/components/ui/misc";
import { useAuth } from "@/features/auth/auth-provider";
import { RequireAuth } from "@/features/auth/guards";
import { formatDateTime } from "@/lib/utils";
import { api, errorMessage } from "@/services/api-client";
import type { SessionInfo, User } from "@/types/api";

function Profile() {
  const { user, reloadUser } = useAuth();
  const form = useForm({ defaultValues: { full_name: user?.full_name ?? "" } });
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      await api<User>("/auth/me", { method: "PATCH", body: v });
      await reloadUser();
      toast.success("Profile updated");
    } catch (e) {
      toast.error(errorMessage(e));
    }
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile</CardTitle>
        <CardDescription>
          {user?.email} {user?.email_verified ? <Badge variant="success">Verified</Badge> : <Badge variant="warning">Not verified</Badge>}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-3">
          <div className="min-w-60 flex-1">
            <Field label="Full name" htmlFor="full_name">
              <Input id="full_name" {...form.register("full_name", { required: true, maxLength: 200 })} />
            </Field>
          </div>
          <Button type="submit" variant="outline" loading={form.formState.isSubmitting}>
            Save
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

const pwSchema = z
  .object({ current_password: z.string().min(1, "Required"), new_password: z.string().min(10, "Use at least 10 characters"), confirm: z.string() })
  .refine((v) => v.new_password === v.confirm, { path: ["confirm"], message: "Passwords do not match" });

function ChangePassword() {
  const [error, setError] = useState<string | null>(null);
  const qc = useQueryClient();
  const form = useForm({ resolver: zodResolver(pwSchema), defaultValues: { current_password: "", new_password: "", confirm: "" } });
  const onSubmit = form.handleSubmit(async ({ current_password, new_password }) => {
    setError(null);
    try {
      await api("/auth/change-password", { method: "POST", body: { current_password, new_password } });
      toast.success("Password changed. Other sessions were signed out.");
      form.reset();
      qc.invalidateQueries({ queryKey: ["sessions"] });
    } catch (e) {
      setError(errorMessage(e));
    }
  });
  const errors = form.formState.errors;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Password</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <FormError message={error} />
          <Field label="Current password" htmlFor="current_password" error={errors.current_password?.message}>
            <Input id="current_password" type="password" autoComplete="current-password" {...form.register("current_password")} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="New password" htmlFor="new_password" error={errors.new_password?.message}>
              <Input id="new_password" type="password" autoComplete="new-password" {...form.register("new_password")} />
            </Field>
            <Field label="Confirm" htmlFor="confirm" error={errors.confirm?.message}>
              <Input id="confirm" type="password" autoComplete="new-password" {...form.register("confirm")} />
            </Field>
          </div>
          <Button type="submit" loading={form.formState.isSubmitting}>
            Change password
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function TwoFactor() {
  const { user, reloadUser } = useAuth();
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [codes, setCodes] = useState<string[] | null>(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Two-factor authentication {user?.mfa_enabled ? <Badge variant="success">On</Badge> : <Badge variant="muted">Off</Badge>}
        </CardTitle>
        <CardDescription>Protect publishing and billing with a code from an authenticator app.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <FormError message={error} />
        {codes ? (
          <div className="space-y-3">
            <p className="text-sm font-medium">Save these recovery codes somewhere safe. Each works once. They will not be shown again.</p>
            <ul className="grid grid-cols-2 gap-2 rounded-md bg-muted p-4 font-mono text-sm">
              {codes.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
            <Button variant="outline" onClick={() => setCodes(null)}>
              I have saved them
            </Button>
          </div>
        ) : user?.mfa_enabled ? (
          <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
            <Field label="Password" htmlFor="mfa-pw">
              <Input id="mfa-pw" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
            <Field label="Current code" htmlFor="mfa-off-code">
              <Input id="mfa-off-code" value={code} onChange={(e) => setCode(e.target.value)} autoComplete="one-time-code" />
            </Field>
            <Button
              variant="destructive"
              loading={busy}
              onClick={() =>
                run(async () => {
                  await api("/auth/mfa/disable", { method: "POST", body: { password, code } });
                  setCode("");
                  setPassword("");
                  await reloadUser();
                  toast.success("Two-factor authentication turned off");
                })
              }
            >
              Turn off
            </Button>
          </div>
        ) : setup ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-6">
              <div className="rounded-lg border bg-white p-3">
                <QRCodeSVG value={setup.otpauth_uri} size={160} />
              </div>
              <div className="space-y-1 text-sm">
                <p>Scan with Google Authenticator, 1Password, Authy or similar.</p>
                <p className="text-muted-foreground">
                  Or enter this key: <code className="break-all font-mono">{setup.secret}</code>
                </p>
              </div>
            </div>
            <div className="flex flex-wrap items-end gap-3">
              <Field label="6-digit code" htmlFor="mfa-code">
                <Input id="mfa-code" value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" />
              </Field>
              <Button
                loading={busy}
                onClick={() =>
                  run(async () => {
                    const res = await api<{ recovery_codes: string[] }>("/auth/mfa/enable", { method: "POST", body: { code } });
                    setCodes(res.recovery_codes);
                    setSetup(null);
                    setCode("");
                    await reloadUser();
                  })
                }
              >
                Verify and turn on
              </Button>
            </div>
          </div>
        ) : (
          <Button
            loading={busy}
            onClick={() => run(async () => setSetup(await api("/auth/mfa/setup", { method: "POST" })))}
          >
            Set up two-factor authentication
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

function Sessions() {
  const qc = useQueryClient();
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: () => api<SessionInfo[]>("/auth/sessions") });
  const revoke = useMutation({
    mutationFn: (id: string) => api(`/auth/sessions/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>Active sessions</CardTitle>
        <CardDescription>Sign out devices you do not recognize.</CardDescription>
      </CardHeader>
      <CardContent>
        {sessions.isLoading ? (
          <Spinner />
        ) : (
          <ul className="divide-y">
            {sessions.data?.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                <div className="min-w-0">
                  <p className="truncate font-medium">{s.user_agent ?? "Unknown device"}</p>
                  <p className="text-muted-foreground">
                    {s.ip_address ?? "unknown IP"} · last active {formatDateTime(s.last_used_at)}
                  </p>
                </div>
                {s.current ? (
                  <Badge variant="success">This device</Badge>
                ) : (
                  <Button variant="ghost" size="sm" loading={revoke.isPending && revoke.variables === s.id} onClick={() => revoke.mutate(s.id)}>
                    Sign out
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export default function SecurityPage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="flex h-14 items-center justify-between border-b bg-card px-4 lg:px-8">
        <Logo href="/app" />
        <Link href="/app" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
          <ArrowLeft className="size-4" /> Back to app
        </Link>
      </header>
      <main className="mx-auto max-w-3xl space-y-6 px-4 py-8">
        <h1 className="text-2xl font-semibold tracking-tight">Account & security</h1>
        <RequireAuth>
          <div className="space-y-6">
            <Profile />
            <TwoFactor />
            <ChangePassword />
            <Sessions />
          </div>
        </RequireAuth>
      </main>
    </div>
  );
}
