"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ExternalLink, Pencil, Plus, Trash2 } from "lucide-react";
import { useParams } from "next/navigation";
import { useDeferredValue, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmDialog, Dialog } from "@/components/ui/dialog";
import { Field, FormError } from "@/components/ui/form";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { Badge, EmptyState, ErrorState, Spinner } from "@/components/ui/misc";
import { useAssets, useDeleteProduct, useProducts, useSaveProduct, type ProductFilters } from "@/features/brands/api";
import { formatPrice } from "@/features/brands/components";
import { useCurrentOrg } from "@/hooks/use-org";
import { errorMessage } from "@/services/api-client";
import type { Product } from "@/types/api";

const CURRENCIES = ["INR", "USD", "EUR", "GBP", "AED", "SGD", "AUD"];

const schema = z.object({
  kind: z.enum(["product", "service"]),
  name: z.string().trim().min(1, "Enter a name").max(200),
  sku: z.string().trim().max(100),
  price: z.union([z.literal(""), z.string().regex(/^\d{1,12}(\.\d{1,2})?$/, "Use a number with up to 2 decimals")]),
  currency: z.string(),
  price_unit: z.string().max(50),
  url: z.union([z.url("Enter a full URL"), z.literal("")]),
  description: z.string().max(5000),
  features: z.string().max(9000),
  image_asset_id: z.string(),
  archived: z.boolean(),
});
type FormValues = z.infer<typeof schema>;

export default function ProductsPage() {
  const { orgId, org, can } = useCurrentOrg();
  const { brandId } = useParams<{ brandId: string }>();
  const [kind, setKind] = useState<ProductFilters["kind"]>();
  const [showArchived, setShowArchived] = useState(false);
  const [search, setSearch] = useState("");
  const q = useDeferredValue(search.trim());
  const products = useProducts(orgId, brandId, { kind, q: q || undefined, status: showArchived ? undefined : "active" });
  const images = useAssets(orgId, brandId);
  const save = useSaveProduct(orgId, brandId);
  const remove = useDeleteProduct(orgId, brandId);
  const [editing, setEditing] = useState<Product | "new" | null>(null);
  const [deleting, setDeleting] = useState<Product | null>(null);
  const [error, setError] = useState<string | null>(null);
  const form = useForm<FormValues>({ resolver: zodResolver(schema) });
  const manage = can("brands.manage");
  const imageChoices = (images.data?.items ?? []).filter((a) => a.kind === "image" || a.kind === "logo");

  const openEditor = (p: Product | "new") => {
    setError(null);
    form.reset(
      p === "new"
        ? { kind: kind ?? "product", name: "", sku: "", price: "", currency: org?.default_currency ?? "USD", price_unit: "",
            url: "", description: "", features: "", image_asset_id: "", archived: false }
        : { kind: p.kind, name: p.name, sku: p.sku ?? "", price: p.price ?? "", currency: p.currency ?? org?.default_currency ?? "USD",
            price_unit: p.price_unit ?? "", url: p.url ?? "", description: p.description ?? "", features: p.features.join("\n"),
            image_asset_id: p.image_asset_id ?? "", archived: p.status === "archived" },
    );
    setEditing(p);
  };

  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await save.mutateAsync({
        id: editing && editing !== "new" ? editing.id : undefined,
        kind: v.kind,
        name: v.name,
        sku: v.sku || null,
        price: v.price || null,
        currency: v.price ? v.currency : null,
        price_unit: v.price_unit || null,
        url: v.url || null,
        description: v.description || null,
        features: v.features.split("\n").map((f) => f.trim()).filter(Boolean).slice(0, 30),
        image_asset_id: v.image_asset_id || null,
        ...(editing !== "new" ? { status: v.archived ? "archived" : "active" } : {}),
      });
      toast.success(`${v.name} saved`);
      setEditing(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  });

  const errors = form.formState.errors;
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Input className="max-w-xs" placeholder="Search name or SKU" aria-label="Search products" value={search} onChange={(e) => setSearch(e.target.value)} />
        <NativeSelect className="w-40" aria-label="Filter by type" value={kind ?? ""} onChange={(e) => setKind((e.target.value || undefined) as ProductFilters["kind"])}>
          <option value="">All types</option>
          <option value="product">Products</option>
          <option value="service">Services</option>
        </NativeSelect>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} /> Include archived
        </label>
        <div className="flex-1" />
        {manage && (
          <Button onClick={() => openEditor("new")}>
            <Plus /> Add product or service
          </Button>
        )}
      </div>
      {products.isLoading ? (
        <Spinner />
      ) : products.isError ? (
        <ErrorState message={errorMessage(products.error)} onRetry={() => products.refetch()} />
      ) : !products.data?.items.length ? (
        <EmptyState
          title={q || kind ? "Nothing matches these filters" : "No products or services yet"}
          description="Ads perform better when they name a real offer with its price and benefits."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {products.data.items.map((p) => (
            <Card key={p.id}>
              <CardContent className="flex gap-4 pt-6">
                {p.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element -- signed storage URL
                  <img src={p.image_url} alt="" className="size-16 shrink-0 rounded-md border object-cover" />
                ) : null}
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-semibold">{p.name}</p>
                    <div className="flex shrink-0 gap-1">
                      <Badge variant="muted" className="capitalize">{p.kind}</Badge>
                      {p.status === "archived" && <Badge variant="warning">Archived</Badge>}
                    </div>
                  </div>
                  <p className="text-sm font-medium">{formatPrice(p)}</p>
                  {p.description && <p className="line-clamp-2 text-sm text-muted-foreground">{p.description}</p>}
                  {p.features.length > 0 && (
                    <ul className="list-inside list-disc text-xs text-muted-foreground">
                      {p.features.slice(0, 4).map((f) => (
                        <li key={f}>{f}</li>
                      ))}
                    </ul>
                  )}
                  <div className="flex items-center justify-between pt-1 text-xs text-muted-foreground">
                    <span>{p.sku ? `SKU ${p.sku}` : ""}</span>
                    <span className="flex gap-1">
                      {p.url && (
                        <a href={p.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">
                          Page <ExternalLink className="size-3" />
                        </a>
                      )}
                      {manage && (
                        <>
                          <Button variant="ghost" size="icon" onClick={() => openEditor(p)} aria-label={`Edit ${p.name}`}>
                            <Pencil />
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => setDeleting(p)} aria-label={`Delete ${p.name}`}>
                            <Trash2 />
                          </Button>
                        </>
                      )}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      {products.data && products.data.total > products.data.items.length && (
        <p className="mt-4 text-sm text-muted-foreground">
          Showing {products.data.items.length} of {products.data.total}. Narrow the search to find more.
        </p>
      )}

      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)} title={editing === "new" ? "Add product or service" : "Edit product or service"}>
        <form onSubmit={onSubmit} className="max-h-[70vh] space-y-4 overflow-y-auto pr-1" noValidate>
          <FormError message={error} />
          <div className="grid grid-cols-2 gap-3">
            <Field label="Type" htmlFor="p-kind">
              <NativeSelect id="p-kind" {...form.register("kind")}>
                <option value="product">Product</option>
                <option value="service">Service</option>
              </NativeSelect>
            </Field>
            <Field label="SKU (optional)" htmlFor="p-sku">
              <Input id="p-sku" {...form.register("sku")} />
            </Field>
          </div>
          <Field label="Name" htmlFor="p-name" error={errors.name?.message}>
            <Input id="p-name" {...form.register("name")} />
          </Field>
          <div className="grid grid-cols-[1fr_6rem_1fr] gap-3">
            <Field label="Price" htmlFor="p-price" error={errors.price?.message}>
              <Input id="p-price" inputMode="decimal" placeholder="Leave blank if on request" {...form.register("price")} />
            </Field>
            <Field label="Currency" htmlFor="p-currency">
              <NativeSelect id="p-currency" {...form.register("currency")}>
                {CURRENCIES.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </NativeSelect>
            </Field>
            <Field label="Per (optional)" htmlFor="p-unit">
              <Input id="p-unit" placeholder="session, month…" {...form.register("price_unit")} />
            </Field>
          </div>
          <Field label="Product page" htmlFor="p-url" error={errors.url?.message}>
            <Input id="p-url" placeholder="https://" {...form.register("url")} />
          </Field>
          <Field label="Description" htmlFor="p-desc">
            <Textarea id="p-desc" rows={3} {...form.register("description")} />
          </Field>
          <Field label="Key benefits" htmlFor="p-features" hint="One per line, up to 30.">
            <Textarea id="p-features" rows={4} {...form.register("features")} />
          </Field>
          <Field label="Image" htmlFor="p-image" hint={imageChoices.length ? undefined : "Upload images in the Assets tab to pick one here."}>
            <NativeSelect id="p-image" {...form.register("image_asset_id")}>
              <option value="">No image</option>
              {imageChoices.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.title || a.original_filename}
                </option>
              ))}
            </NativeSelect>
          </Field>
          {editing !== "new" && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" {...form.register("archived")} /> Archived
            </label>
          )}
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
            Save
          </Button>
        </form>
      </Dialog>
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Delete ${deleting?.name ?? ""}?`}
        description="Campaigns created later will no longer be able to reference it."
        confirmLabel="Delete"
        destructive
        loading={remove.isPending}
        onConfirm={async () => {
          try {
            await remove.mutateAsync(deleting!.id);
            setDeleting(null);
          } catch (e) {
            toast.error(errorMessage(e));
          }
        }}
      />
    </>
  );
}
