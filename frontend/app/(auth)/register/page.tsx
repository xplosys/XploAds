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
import type { TokenResponse } from "@/types/api";

const schema = z
  .object({
    full_name: z.string().trim().min(1, "Enter your name").max(200),
    email: z.email("Enter a valid email"),
    password: z.string().min(10, "Use at least 10 characters").max(128),
    confirm: z.string(),
  })
  .refine((v) => v.password === v.confirm, { path: ["confirm"], message: "Passwords do not match" });

function RegisterForm() {
  const { signIn } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: { full_name: "", email: "", password: "", confirm: "" },
  });
  const { errors, isSubmitting } = form.formState;

  const onSubmit = form.handleSubmit(async ({ full_name, email, password }) => {
    setError(null);
    try {
      const res = await api<TokenResponse>("/auth/register", { method: "POST", body: { full_name, email, password }, auth: false });
      await signIn(res.access_token); // the guard then navigates to `next` or onboarding
    } catch (e) {
      setError(errorMessage(e));
    }
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create your account</CardTitle>
        <CardDescription>Start with your business or agency. No credit card required.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <FormError message={error} />
          <Field label="Full name" htmlFor="full_name" error={errors.full_name?.message}>
            <Input id="full_name" autoComplete="name" {...form.register("full_name")} />
          </Field>
          <Field label="Work email" htmlFor="email" error={errors.email?.message}>
            <Input id="email" type="email" autoComplete="email" {...form.register("email")} />
          </Field>
          <Field label="Password" htmlFor="password" error={errors.password?.message} hint="At least 10 characters.">
            <Input id="password" type="password" autoComplete="new-password" {...form.register("password")} />
          </Field>
          <Field label="Confirm password" htmlFor="confirm" error={errors.confirm?.message}>
            <Input id="confirm" type="password" autoComplete="new-password" {...form.register("confirm")} />
          </Field>
          <Button type="submit" className="w-full" loading={isSubmitting}>
            Create account
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-primary hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      </CardContent>
    </Card>
  );
}

function Guarded() {
  const next = safeNext(useSearchParams().get("next"), "/onboarding");
  return (
    <RedirectIfAuthenticated to={next}>
      <RegisterForm />
    </RedirectIfAuthenticated>
  );
}

export default function RegisterPage() {
  return (
    <Suspense>
      <Guarded />
    </Suspense>
  );
}
