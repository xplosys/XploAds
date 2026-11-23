"use client";

import { ArrowLeft, Star, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { Badge, ErrorState, Spinner } from "@/components/ui/misc";
import { useBrand, useBrandAction } from "@/features/brands/api";
import { BrandMark } from "@/features/brands/components";
import { useCurrentOrg } from "@/hooks/use-org";
import { cn } from "@/lib/utils";
import { errorMessage } from "@/services/api-client";

export default function BrandLayout({ children }: { children: React.ReactNode }) {
  const { orgId, can } = useCurrentOrg();
  const { brandId } = useParams<{ brandId: string }>();
  const pathname = usePathname();
  const router = useRouter();
  const brand = useBrand(orgId, brandId);
  const action = useBrandAction(orgId);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (brand.isLoading) return <Spinner label="Loading brand" />;
  if (brand.isError || !brand.data)
    return <ErrorState message={errorMessage(brand.error, "This brand could not be loaded.")} onRetry={() => brand.refetch()} />;

  const b = brand.data;
  const base = `/app/${orgId}/brands/${brandId}`;
  const tabs = [
    { href: base, label: "Profile" },
    { href: `${base}/guidelines`, label: "Guidelines", count: b.counts.guidelines },
    { href: `${base}/products`, label: "Products & services", count: b.counts.products },
    { href: `${base}/assets`, label: "Assets", count: b.counts.assets },
  ];
  const manage = can("brands.manage");

  const run = async (kind: "default" | "delete") => {
    try {
      await action.mutateAsync({ brandId, action: kind });
      if (kind === "delete") {
        toast.success(`${b.name} deleted`);
        router.replace(`/app/${orgId}/brands`);
      } else {
        toast.success(`${b.name} is now the default brand`);
        brand.refetch();
      }
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  return (
    <>
      <Link href={`/app/${orgId}/brands`} className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> All brands
      </Link>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <BrandMark name={b.name} url={b.logo_url} size="lg" />
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
              {b.name}
              {b.is_default && <Badge>Default</Badge>}
              {b.status === "archived" && <Badge variant="muted">Archived</Badge>}
            </h1>
            <p className="text-sm text-muted-foreground">{b.tagline || "Add a tagline in the profile"}</p>
          </div>
        </div>
        {manage && (
          <div className="flex gap-2">
            {!b.is_default && b.status === "active" && (
              <Button variant="outline" size="sm" onClick={() => run("default")} loading={action.isPending}>
                <Star /> Make default
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={() => setConfirmDelete(true)}>
              <Trash2 /> Delete
            </Button>
          </div>
        )}
      </div>
      <nav className="mb-6 flex gap-1 overflow-x-auto border-b" aria-label="Brand sections">
        {tabs.map((t) => {
          const active = t.href === base ? pathname === base : pathname.startsWith(t.href);
          return (
            <Link
              key={t.href}
              href={t.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "-mb-px whitespace-nowrap border-b-2 border-transparent px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground",
                active && "border-primary text-foreground",
              )}
            >
              {t.label}
              {t.count !== undefined && (
                <span className="ml-1.5 text-xs text-muted-foreground" aria-label={`(${t.count})`}>
                  {t.count}
                </span>
              )}
            </Link>
          );
        })}
      </nav>
      {children}
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`Delete ${b.name}?`}
        description="Its guidelines, products and uploaded assets will be removed. This cannot be undone."
        confirmLabel="Delete brand"
        destructive
        loading={action.isPending}
        onConfirm={() => run("delete")}
      />
    </>
  );
}
