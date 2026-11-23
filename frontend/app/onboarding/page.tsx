"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Building2, Network, Landmark } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FormError } from "@/components/ui/form";
import { Input, NativeSelect } from "@/components/ui/input";
import { RequireAuth } from "@/features/auth/guards";
import { useCreateOrganization } from "@/features/organizations/api";
import { errorMessage } from "@/services/api-client";
import { cn } from "@/lib/utils";

const TYPES = [
  { value: "business", label: "Business", icon: Building2, text: "One company advertising its own products or services." },
  { value: "agency", label: "Agency", icon: Network, text: "Manage campaigns for multiple client organizations." },
  { value: "enterprise", label: "Enterprise", icon: Landmark, text: "Several departments or teams with their own workspaces." },
] as const;

const schema = z.object({
  name: z.string().trim().min(2, "Enter your organization's name").max(200),
  tenant_type: z.enum(["business", "agency", "enterprise"]),
  industry: z.string().max(100).optional(),
  country_code: z.string().regex(/^[A-Z]{2}$/).optional().or(z.literal("")),
  default_currency: z.string().regex(/^[A-Z]{3}$/),
});

function OnboardingForm() {
  const router = useRouter();
  const create = useCreateOrganization();
  const [error, setError] = useState<string | null>(null);
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: { name: "", tenant_type: "business" as const, industry: "", country_code: "", default_currency: "INR" },
  });
  const type = useWatch({ control: form.control, name: "tenant_type" });

  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      const org = await create.mutateAsync({
        ...v,
        industry: v.industry || undefined,
        country_code: v.country_code || undefined,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      });
      window.localStorage.setItem("xploads.activeOrg", org.id);
      router.replace(`/app/${org.id}`);
    } catch (e) {
      setError(errorMessage(e));
    }
  });

  return (
    <form onSubmit={onSubmit} className="space-y-6" noValidate>
      <FormError message={error} />
      <fieldset className="grid gap-3 sm:grid-cols-3">
        <legend className="mb-2 text-sm font-medium">Account type</legend>
        {TYPES.map((t) => (
          <label
            key={t.value}
            className={cn(
              "cursor-pointer rounded-lg border p-4 transition-colors hover:bg-muted",
              type === t.value && "border-primary bg-secondary ring-1 ring-primary",
            )}
          >
            <input type="radio" value={t.value} className="sr-only" {...form.register("tenant_type")} />
            <t.icon className="mb-2 size-5 text-primary" aria-hidden />
            <span className="block text-sm font-semibold">{t.label}</span>
            <span className="mt-1 block text-xs text-muted-foreground">{t.text}</span>
          </label>
        ))}
      </fieldset>
      <Field label={type === "agency" ? "Agency name" : "Organization name"} htmlFor="name" error={form.formState.errors.name?.message}>
        <Input id="name" autoComplete="organization" {...form.register("name")} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Industry" htmlFor="industry">
          <Input id="industry" placeholder="e.g. Healthcare" {...form.register("industry")} />
        </Field>
        <Field label="Country (ISO code)" htmlFor="country_code" error={form.formState.errors.country_code ? "Use a 2-letter code, e.g. IN" : undefined}>
          <Input id="country_code" placeholder="IN" maxLength={2} {...form.register("country_code", { setValueAs: (v: string) => v.toUpperCase() })} />
        </Field>
        <Field label="Currency" htmlFor="default_currency">
          <NativeSelect id="default_currency" {...form.register("default_currency")}>
            {["INR", "USD", "EUR", "GBP", "AED", "SGD", "AUD"].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </NativeSelect>
        </Field>
      </div>
      <Button type="submit" size="lg" className="w-full" loading={form.formState.isSubmitting}>
        Create organization
      </Button>
    </form>
  );
}

export default function OnboardingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-secondary/60 to-background px-4 py-12">
      <div className="mx-auto max-w-2xl">
        <div className="mb-8 flex justify-center">
          <Logo href="/app" />
        </div>
        <RequireAuth>
          <Card>
            <CardHeader>
              <CardTitle>Set up your organization</CardTitle>
              <CardDescription>
                Your organization holds your brands, Meta connections, campaigns and leads. You can invite your team next.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <OnboardingForm />
            </CardContent>
          </Card>
        </RequireAuth>
      </div>
    </div>
  );
}
