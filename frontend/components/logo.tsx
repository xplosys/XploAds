import Link from "next/link";

export function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="inline-flex items-center gap-2 font-semibold tracking-tight" aria-label="XploAds home">
      <span className="grid size-8 place-items-center rounded-lg bg-gradient-to-br from-primary to-accent text-sm font-bold text-white">
        X
      </span>
      <span className="text-lg">
        Xplo<span className="text-primary">Ads</span>
      </span>
    </Link>
  );
}
