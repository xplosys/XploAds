"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Palette, Plus, Star } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Field, FormError } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Badge, EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui/misc";
import { useBrands, useCreateBrand } from "@/features/brands/api";
import { BrandMark } from "@/features/brands/components";
import { useCurrentOrg } from "@/hooks/use-org";
import { errorMessage } from "@/services/api-client";

const schema = z.object({
  name: z.string().trim().min(2, "Enter the brand name").max(200),
  tagline: z.string().max(300),
  industry: z.string().max(100),
});

export default function BrandsPage() {
  const { orgId, can } = useCurrentOrg();
  const router = useRouter();
  const [showArchived, setShowArchived] = useState(false);
  const brands = useBrands(orgId, showArchived, can("brands.read"));
  const create = useCreateBrand(orgId);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const form = useForm({ resolver: zodResolver(schema), defaultValues: { name: "", tagline: "", industry: "" } });

  if (!can("brands.read")) return <EmptyState title="You don't have access to brand profiles" />;

  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      const brand = await create.mutateAsync({
        name: v.name,
        tagline: v.tagline || null,
        industry: v.industry || null,
      });
      toast.success(`${brand.name} created`);
      setOpen(false);
      form.reset();
      router.push(`/app/${orgId}/brands/${brand.id}`);
    } catch (e) {
      setError(errorMessage(e));
    }
  });

  return (
    <>
      <PageHeader
        title="Brands"
        description="Brand kits feed every creative and campaign: voice, colours, products and approved assets."
        actions={
          can("brands.manage") && (
            <Button onClick={() => setOpen(true)}>
              <Plus /> New brand
            </Button>
          )
        }
      />
      <label className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
        <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
        Show archived brands
      </label>
      {brands.isLoading ? (
        <Spinner />
      ) : brands.isError ? (
        <ErrorState message={errorMessage(brands.error)} onRetry={() => brands.refetch()} />
      ) : !brands.data?.length ? (
        <EmptyState
          title="No brands yet"
          description="Create a brand profile with its voice, colours and products before generating creatives."
          action={
            can("brands.manage") && (
              <Button onClick={() => setOpen(true)}>
                <Palette /> Create your first brand
              </Button>
            )
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {brands.data.map((b) => (
            <Link key={b.id} href={`/app/${orgId}/brands/${b.id}`} className="group">
              <Card className="h-full transition-shadow group-hover:shadow-md">
                <CardContent className="flex gap-4 pt-6">
                  <BrandMark name={b.name} url={b.logo_url} />
                  <div className="min-w-0 space-y-1">
                    <p className="flex items-center gap-2 font-semibold">
                      <span className="truncate">{b.name}</span>
                      {b.is_default && (
                        <Star className="size-3.5 fill-current text-warning" aria-label="Default brand" />
                      )}
                    </p>
                    <p className="line-clamp-2 text-sm text-muted-foreground">{b.tagline || b.industry || "No tagline yet"}</p>
                    {b.status === "archived" && <Badge variant="muted">Archived</Badge>}
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
      <Dialog open={open} onOpenChange={setOpen} title="New brand">
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <FormError message={error} />
          <Field label="Brand name" htmlFor="brand-name" error={form.formState.errors.name?.message}>
            <Input id="brand-name" {...form.register("name")} />
          </Field>
          <Field label="Tagline" htmlFor="brand-tagline">
            <Input id="brand-tagline" {...form.register("tagline")} />
          </Field>
          <Field label="Industry" htmlFor="brand-industry">
            <Input id="brand-industry" {...form.register("industry")} />
          </Field>
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
            Create brand
          </Button>
        </form>
      </Dialog>
    </>
  );
}
