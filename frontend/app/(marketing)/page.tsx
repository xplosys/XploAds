import { BarChart3, MessageCircle, ShieldCheck, Sparkles, Target, Users } from "lucide-react";
import Link from "next/link";

import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";

const FEATURES = [
  { icon: Sparkles, title: "AI Creative Studio", text: "Copy, images, carousels and short videos generated from your brief and brand kit." },
  { icon: Target, title: "Campaign strategy", text: "AI-recommended objectives, audiences and budgets you review before anything goes live." },
  { icon: ShieldCheck, title: "You stay in control", text: "Nothing publishes and no budget changes without your approval. Every action is audited." },
  { icon: MessageCircle, title: "Leads & WhatsApp", text: "Lead Ads and Click-to-WhatsApp enquiries land in one CRM, qualified and assigned." },
  { icon: BarChart3, title: "Performance insights", text: "Spend, CPL and conversions in one place, with recommendations you can act on." },
  { icon: Users, title: "Built for agencies", text: "Separate, isolated client workspaces with their own brands, Meta assets and leads." },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5">
        <Logo />
        <nav className="flex items-center gap-2">
          <Button asChild variant="ghost">
            <Link href="/login">Sign in</Link>
          </Button>
          <Button asChild>
            <Link href="/register">Get started</Link>
          </Button>
        </nav>
      </header>
      <section className="mx-auto max-w-4xl px-4 pb-16 pt-16 text-center">
        <p className="mb-4 inline-block rounded-full bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground">
          AI advertising automation for Facebook & Instagram
        </p>
        <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">
          From brief to published ads, <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">with you in control</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
          XploAds plans campaigns, produces on-brand creatives, publishes through Meta after your approval, and turns
          responses into qualified leads. Modules are rolling out in phases; accounts, teams and agency workspaces are live today.
        </p>
        <div className="mt-8 flex justify-center gap-3">
          <Button asChild size="lg">
            <Link href="/register">Create your account</Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="/login">Sign in</Link>
          </Button>
        </div>
      </section>
      <section className="mx-auto grid max-w-6xl gap-4 px-4 pb-24 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f) => (
          <div key={f.title} className="rounded-xl border bg-card p-6 shadow-sm">
            <f.icon className="mb-3 size-6 text-primary" aria-hidden />
            <h2 className="font-semibold">{f.title}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{f.text}</p>
          </div>
        ))}
      </section>
      <footer className="border-t py-8 text-center text-sm text-muted-foreground">© Xplosys · XploAds</footer>
    </div>
  );
}
