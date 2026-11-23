"use client";

import { CheckCircle2, Circle } from "lucide-react";
import Link from "next/link";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, PageHeader } from "@/components/ui/misc";
import { useAuth } from "@/features/auth/auth-provider";
import { useBrands } from "@/features/brands/api";
import { useMembers, useWorkspaces } from "@/features/organizations/api";
import { useCurrentOrg } from "@/hooks/use-org";

const ROADMAP = [
  { phase: 3, title: "AI providers & usage", text: "Gemini, OpenAI, DeepSeek with BYOK and metered credits." },
  { phase: 4, title: "AI Creative Studio", text: "Copy, images, carousels and videos generated from your brief." },
  { phase: 5, title: "Meta campaigns", text: "Connect Pages, Instagram and ad accounts; approve and publish." },
  { phase: 6, title: "Leads CRM & WhatsApp", text: "Lead Ads and Click-to-WhatsApp enquiries in one pipeline." },
];

export default function DashboardPage() {
  const { orgId, org, can } = useCurrentOrg();
  const { user } = useAuth();
  const members = useMembers(orgId);
  const workspaces = useWorkspaces(orgId);
  const brands = useBrands(orgId, false, can("brands.read"));
  if (!org) return null;

  const steps = [
    { done: !!user?.email_verified, label: "Verify your email address", href: undefined },
    { done: !!user?.mfa_enabled, label: "Turn on two-factor authentication", href: "/account/security" },
    {
      done: (members.data?.length ?? 0) > 1,
      label: "Invite your team",
      href: can("members.invite") ? `/app/${orgId}/members` : undefined,
    },
    {
      done: (brands.data?.length ?? 0) > 0,
      label: "Create your brand kit",
      href: can("brands.read") ? `/app/${orgId}/brands` : undefined,
    },
    {
      done: (workspaces.data?.length ?? 0) > 1,
      label: "Organize work into workspaces",
      href: can("workspaces.manage") ? `/app/${orgId}/workspaces` : undefined,
    },
  ];

  return (
    <>
      <PageHeader title={`Welcome, ${user?.full_name.split(" ")[0] ?? ""}`} description={`${org.name} · ${org.default_currency} · ${org.timezone}`} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Get set up</CardTitle>
            <CardDescription>A secure foundation before you connect Meta and start spending.</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {steps.map((s) => (
                <li key={s.label} className="flex items-center gap-3 text-sm">
                  {s.done ? (
                    <CheckCircle2 className="size-5 text-success" aria-label="Done" />
                  ) : (
                    <Circle className="size-5 text-muted-foreground" aria-label="Not done" />
                  )}
                  {s.href && !s.done ? (
                    <Link href={s.href} className="font-medium text-primary hover:underline">
                      {s.label}
                    </Link>
                  ) : (
                    <span className={s.done ? "text-muted-foreground line-through" : ""}>{s.label}</span>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Coming next</CardTitle>
            <CardDescription>These modules are on the roadmap and not available yet.</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {ROADMAP.map((r) => (
                <li key={r.title} className="flex items-start justify-between gap-3 text-sm">
                  <div>
                    <p className="font-medium">{r.title}</p>
                    <p className="text-muted-foreground">{r.text}</p>
                  </div>
                  <Badge variant="muted">Phase {r.phase}</Badge>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
