"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Field, FormError } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui/misc";
import { useClients, useCreateClient } from "@/features/organizations/api";
import { useCurrentOrg } from "@/hooks/use-org";
import { formatDate } from "@/lib/utils";
import { errorMessage } from "@/services/api-client";

const schema = z.object({ name: z.string().trim().min(2, "Enter the client's name").max(200), industry: z.string().max(100).optional() });

export default function ClientsPage() {
  const { orgId, org, can } = useCurrentOrg();
  const isAgency = org?.tenant_type === "agency";
  const clients = useClients(orgId, isAgency && can("agency.clients.access"));
  const create = useCreateClient(orgId);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const form = useForm({ resolver: zodResolver(schema), defaultValues: { name: "", industry: "" } });

  if (!isAgency) return <EmptyState title="Client organizations are available to agency accounts" />;

  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await create.mutateAsync({ name: v.name, industry: v.industry || undefined });
      await clients.refetch();
      toast.success(`${v.name} added`);
      form.reset();
      setOpen(false);
    } catch (e) {
      setError(errorMessage(e));
    }
  });

  return (
    <>
      <PageHeader
        title="Client organizations"
        description="Each client has its own isolated brands, Meta connections, campaigns and leads."
        actions={
          can("agency.clients.create") && (
            <Button onClick={() => setOpen(true)}>
              <Plus /> Add client
            </Button>
          )
        }
      />
      {clients.isLoading ? (
        <Spinner />
      ) : clients.isError ? (
        <ErrorState message={errorMessage(clients.error)} onRetry={() => clients.refetch()} />
      ) : !clients.data?.length ? (
        <EmptyState title="No clients yet" description="Add your first client to manage their campaigns from this agency account." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {clients.data.map((c) => (
            <Card key={c.id}>
              <CardContent className="space-y-2 pt-6">
                <p className="font-semibold">{c.name}</p>
                <p className="text-sm text-muted-foreground">{c.industry || "Industry not set"}</p>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Added {formatDate(c.created_at)}</span>
                  <Link href={`/app/${c.id}`} className="inline-flex items-center gap-1 font-medium text-primary hover:underline">
                    Open <ArrowRight className="size-3" />
                  </Link>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      <Dialog open={open} onOpenChange={setOpen} title="Add client organization">
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <FormError message={error} />
          <Field label="Client name" htmlFor="client-name" error={form.formState.errors.name?.message}>
            <Input id="client-name" {...form.register("name")} />
          </Field>
          <Field label="Industry" htmlFor="client-industry">
            <Input id="client-industry" {...form.register("industry")} />
          </Field>
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
            Add client
          </Button>
        </form>
      </Dialog>
    </>
  );
}
