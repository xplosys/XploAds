"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FormError } from "@/components/ui/form";
import { Input, NativeSelect } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/misc";
import { useUpdateOrganization } from "@/features/organizations/api";
import { useCurrentOrg } from "@/hooks/use-org";
import { errorMessage } from "@/services/api-client";

const schema = z.object({
  name: z.string().trim().min(2).max(200),
  industry: z.string().max(100),
  website: z.union([z.url("Enter a full URL, e.g. https://example.com"), z.literal("")]),
  country_code: z.union([z.string().regex(/^[A-Z]{2}$/, "Use a 2-letter code"), z.literal("")]),
  timezone: z.string().min(1).max(64),
  default_currency: z.string().regex(/^[A-Z]{3}$/),
});

export default function OrgSettingsPage() {
  const { orgId, org, can } = useCurrentOrg();
  const update = useUpdateOrganization(orgId);
  const [error, setError] = useState<string | null>(null);
  const editable = can("organization.update");
  const form = useForm({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (org)
      form.reset({
        name: org.name,
        industry: org.industry ?? "",
        website: org.website ?? "",
        country_code: org.country_code ?? "",
        timezone: org.timezone,
        default_currency: org.default_currency,
      });
  }, [org, form]);

  if (!org) return null;
  const errors = form.formState.errors;
  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await update.mutateAsync({
        ...v,
        industry: v.industry || null,
        website: v.website || null,
        country_code: v.country_code || null,
      });
      toast.success("Organization updated");
    } catch (e) {
      setError(errorMessage(e));
    }
  });

  return (
    <>
      <PageHeader title="Organization settings" description={`Slug: ${org.slug}`} />
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Used for reports, invoices and as defaults for new campaigns.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <FormError message={error} />
            <fieldset disabled={!editable} className="space-y-4">
              <Field label="Name" htmlFor="name" error={errors.name?.message}>
                <Input id="name" {...form.register("name")} />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Industry" htmlFor="industry">
                  <Input id="industry" {...form.register("industry")} />
                </Field>
                <Field label="Website" htmlFor="website" error={errors.website?.message}>
                  <Input id="website" placeholder="https://" {...form.register("website")} />
                </Field>
                <Field label="Country (ISO code)" htmlFor="country_code" error={errors.country_code?.message}>
                  <Input id="country_code" maxLength={2} {...form.register("country_code", { setValueAs: (v: string) => v.toUpperCase() })} />
                </Field>
                <Field label="Default currency" htmlFor="default_currency">
                  <NativeSelect id="default_currency" {...form.register("default_currency")}>
                    {["INR", "USD", "EUR", "GBP", "AED", "SGD", "AUD"].map((c) => (
                      <option key={c}>{c}</option>
                    ))}
                  </NativeSelect>
                </Field>
              </div>
              <Field label="Time zone" htmlFor="timezone" error={errors.timezone?.message}>
                <Input id="timezone" {...form.register("timezone")} />
              </Field>
            </fieldset>
            {editable ? (
              <Button type="submit" loading={form.formState.isSubmitting}>
                Save changes
              </Button>
            ) : (
              <p className="text-sm text-muted-foreground">You have read-only access to these settings.</p>
            )}
          </form>
        </CardContent>
      </Card>
    </>
  );
}
