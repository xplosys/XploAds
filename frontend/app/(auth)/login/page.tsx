"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FormError } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/features/auth/auth-provider";
import { RedirectIfAuthenticated, safeNext } from "@/features/auth/guards";
import { api, errorMessage } from "@/services/api-client";
import type { MfaChallengeResponse, TokenResponse } from "@/types/api";

const schema = z.object({
  email: z.email("Enter a valid email"),
  password: z.string().min(1, "Enter your password"),
});
const mfaSchema = z.object({ code: z.string().min(6, "Enter the 6-digit code or a recovery code") });

function LoginForm() {
  const { signIn } = useAuth();
  const next = safeNext(useSearchParams().get("next"));
  const [error, setError] = useState<string | null>(null);
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const form = useForm({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } });
  const mfaForm = useForm({ resolver: zodResolver(mfaSchema), defaultValues: { code: "" } });

  // After sign-in the RedirectIfAuthenticated guard navigates to `next`.
  const finish = (token: string) => signIn(token);

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      const res = await api<TokenResponse | MfaChallengeResponse>("/auth/login", { method: "POST", body: values, auth: false });
      if (res.mfa_required) setMfaToken(res.mfa_token);
      else await finish(res.access_token);
    } catch (e) {
      setError(errorMessage(e));
    }
  });

  const onMfa = mfaForm.handleSubmit(async ({ code }) => {
    setError(null);
    try {
      const res = await api<TokenResponse>("/auth/mfa/verify", { method: "POST", body: { mfa_token: mfaToken, code }, auth: false });
      await finish(res.access_token);
    } catch (e) {
      setError(errorMessage(e));
      if (e instanceof Error && "code" in e && (e as { code: string }).code === "mfa_expired") setMfaToken(null);
    }
  });

  if (mfaToken) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Two-factor authentication</CardTitle>
          <CardDescription>Enter the code from your authenticator app, or one of your recovery codes.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onMfa} className="space-y-4" noValidate>
            <FormError message={error} />
            <Field label="Authentication code" htmlFor="code" error={mfaForm.formState.errors.code?.message}>
              <Input id="code" autoComplete="one-time-code" inputMode="text" autoFocus {...mfaForm.register("code")} />
            </Field>
            <Button type="submit" className="w-full" loading={mfaForm.formState.isSubmitting}>
              Verify and sign in
            </Button>
            <button type="button" className="w-full text-sm text-muted-foreground hover:underline" onClick={() => setMfaToken(null)}>
              Use a different account
            </button>
          </form>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Sign in to XploAds</CardTitle>
        <CardDescription>Welcome back. Manage your campaigns, creatives and leads.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <FormError message={error} />
          <Field label="Email" htmlFor="email" error={form.formState.errors.email?.message}>
            <Input id="email" type="email" autoComplete="email" {...form.register("email")} />
          </Field>
          <Field label="Password" htmlFor="password" error={form.formState.errors.password?.message}>
            <Input id="password" type="password" autoComplete="current-password" {...form.register("password")} />
          </Field>
          <div className="flex justify-end">
            <Link href="/forgot-password" className="text-sm text-primary hover:underline">
              Forgot password?
            </Link>
          </div>
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
            Sign in
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            New to XploAds?{" "}
            <Link href={`/register${next !== "/app" ? `?next=${encodeURIComponent(next)}` : ""}`} className="font-medium text-primary hover:underline">
              Create an account
            </Link>
          </p>
        </form>
      </CardContent>
    </Card>
  );
}

function Guarded() {
  const next = safeNext(useSearchParams().get("next"));
  return (
    <RedirectIfAuthenticated to={next}>
      <LoginForm />
    </RedirectIfAuthenticated>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <Guarded />
    </Suspense>
  );
}
