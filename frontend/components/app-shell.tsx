"use client";

import { ArrowLeft, Building2, FolderKanban, LayoutDashboard, LogOut, Menu, Network, Palette, ScrollText, Settings, Shield, Users, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/input";
import { Badge, ErrorState, Spinner } from "@/components/ui/misc";
import { useAuth } from "@/features/auth/auth-provider";
import { useCurrentOrg } from "@/hooks/use-org";
import { cn } from "@/lib/utils";
import { api, errorMessage } from "@/services/api-client";

function VerifyBanner() {
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  if (!user || user.email_verified) return null;
  const resend = async () => {
    setBusy(true);
    try {
      await api("/auth/resend-verification", { method: "POST" });
      toast.success(`Verification link sent to ${user.email}`);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-warning/40 bg-warning/10 px-6 py-2 text-sm">
      <span>Verify your email address to invite teammates. Check your inbox for the link.</span>
      <Button size="sm" variant="outline" onClick={resend} loading={busy}>
        Resend link
      </Button>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { orgId, org, orgs, can } = useCurrentOrg();
  const { user, signOut } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (org) window.localStorage.setItem("xploads.activeOrg", org.id);
  }, [org]);

  if (orgs.isLoading) return <Spinner label="Loading organization" />;
  if (orgs.isError) return <ErrorState message={errorMessage(orgs.error)} onRetry={() => orgs.refetch()} />;
  if (!org)
    return (
      <div className="mx-auto max-w-md py-20">
        <ErrorState message="This organization does not exist or you no longer have access to it." />
        <div className="mt-4 text-center">
          <Link className="text-sm text-primary hover:underline" href="/app">
            Go to my organizations
          </Link>
        </div>
      </div>
    );

  const base = `/app/${orgId}`;
  const nav = [
    { href: base, label: "Dashboard", icon: LayoutDashboard, show: true },
    { href: `${base}/brands`, label: "Brands", icon: Palette, show: can("brands.read") },
    { href: `${base}/workspaces`, label: "Workspaces", icon: FolderKanban, show: can("workspaces.read") },
    { href: `${base}/members`, label: "Team", icon: Users, show: can("members.read") },
    { href: `${base}/clients`, label: "Clients", icon: Network, show: org.tenant_type === "agency" && can("agency.clients.access") },
    { href: `${base}/settings`, label: "Organization", icon: Settings, show: can("organization.read") },
    { href: `${base}/audit`, label: "Audit log", icon: ScrollText, show: can("audit.read") },
  ].filter((n) => n.show);

  const members = orgs.data!.filter((o) => o.access === "member");
  const parentAgency = org.parent_tenant_id ? orgs.data!.find((o) => o.id === org.parent_tenant_id) : undefined;
  const clients = orgs.data!.filter((o) => o.access === "agency");

  const sidebar = (
    <div className="flex h-full flex-col gap-6 p-4">
      <Logo href="/app" />
      <div className="space-y-1.5">
        <label htmlFor="org-switcher" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Organization
        </label>
        <NativeSelect id="org-switcher" value={org.id} onChange={(e) => router.push(`/app/${e.target.value}`)}>
          <optgroup label="My organizations">
            {members.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </optgroup>
          {clients.length > 0 && (
            <optgroup label="Agency clients">
              {clients.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </optgroup>
          )}
        </NativeSelect>
        <Link href="/onboarding" className="block text-xs text-primary hover:underline">
          + New organization
        </Link>
      </div>
      <nav className="flex-1 space-y-1" aria-label="Main" onClick={() => setOpen(false)}>
        {nav.map((n) => {
          const active = n.href === base ? pathname === base : pathname.startsWith(n.href);
          return (
            <Link
              key={n.href}
              href={n.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground",
                active && "bg-secondary text-secondary-foreground",
              )}
            >
              <n.icon className="size-4" aria-hidden />
              {n.label}
            </Link>
          );
        })}
      </nav>
      <div className="space-y-1 border-t pt-4">
        <Link href="/account/security" className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted">
          <Shield className="size-4" aria-hidden /> Account & security
        </Link>
        <button
          onClick={async () => {
            await signOut();
            router.replace("/login");
          }}
          className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted"
        >
          <LogOut className="size-4" aria-hidden /> Sign out
        </button>
        <p className="truncate px-3 pt-2 text-xs text-muted-foreground" title={user?.email}>
          {user?.full_name} · {user?.email}
        </p>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[260px_1fr]">
      <aside className="hidden border-r bg-card lg:block">{sidebar}</aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 bg-card shadow-xl">{sidebar}</aside>
        </div>
      )}
      <div className="min-w-0">
        <header className="flex h-14 items-center gap-3 border-b bg-card px-4 lg:px-8">
          <button className="lg:hidden" onClick={() => setOpen(!open)} aria-label="Toggle navigation">
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
          <Building2 className="size-4 text-muted-foreground" aria-hidden />
          <span className="truncate font-medium">{org.name}</span>
          <Badge variant="muted" className="capitalize">
            {org.tenant_type}
          </Badge>
          {org.access === "agency" && <Badge>Agency access</Badge>}
          {parentAgency && (
            <Link
              href={`/app/${parentAgency.id}/clients`}
              className="ml-auto inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="size-4" aria-hidden /> Back to {parentAgency.name}
            </Link>
          )}
        </header>
        <VerifyBanner />
        <main className="mx-auto max-w-6xl px-4 py-8 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
