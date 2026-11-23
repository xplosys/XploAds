"use client";

import type { Product } from "@/types/api";

export function BrandMark({ name, url, size = "md" }: { name: string; url: string | null; size?: "md" | "lg" }) {
  const cls = size === "lg" ? "size-16 text-xl" : "size-11 text-base";
  if (url)
    // eslint-disable-next-line @next/next/no-img-element -- signed storage URL, not optimisable by next/image
    return <img src={url} alt={`${name} logo`} className={`${cls} rounded-lg border bg-white object-contain p-1`} />;
  return (
    <div className={`${cls} flex items-center justify-center rounded-lg bg-secondary font-semibold text-secondary-foreground`} aria-hidden>
      {name.slice(0, 1).toUpperCase()}
    </div>
  );
}

export function formatPrice(p: Pick<Product, "price" | "currency" | "price_unit">) {
  if (p.price === null) return "Price on request";
  const amount = new Intl.NumberFormat(undefined, { style: "currency", currency: p.currency ?? "USD" }).format(Number(p.price));
  return p.price_unit ? `${amount} / ${p.price_unit}` : amount;
}
