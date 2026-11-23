"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FormError } from "@/components/ui/form";
import { Spinner } from "@/components/ui/misc";
import { useAuth } from "@/features/auth/auth-provider";
import { api, errorMessage } from "@/services/api-client";
import type { InvitationPreview, Organization } from "@/types/api";

function Accept() {
  const token = useSearchParams().get("token") ?? "";
  const { status, user } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const preview = useQuery({
    queryKey: ["invitation", token],
    queryFn: () => api<InvitationPreview>(`/invitations/preview?token=${encodeURIComponent(token)}`, { auth: false }),
    enabled: token.length > 10,
    retry: false,
  });

  if (!token) return <FormError message="This invitation link is incomplete." />;
  if (preview.isLoading || status === "loading") return <Spinner />;
  if (preview.isError) return <FormError message={errorMessage(preview.error)} />;
  const inv = preview.data!;
  const here = `/invitations/accept?token=${encodeURIComponent(token)}`;

  const accept = async () => {
    setBusy(true);
    setError(null);
    try {
      const org = await api<Organization>("/invitations/accept", { method: "POST", body: { token } });
      await qc.invalidateQueries({ queryKey: ["organizations"] });
      window.localStorage.setItem("xploads.activeOrg", org.id);
      router.replace(`/app/${org.id}`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-sm">
        <strong>{inv.inviter_name ?? "A teammate"}</strong> invited <strong>{inv.email}</strong> to join{" "}
        <strong>{inv.organization_name}</strong> as <strong>{inv.role_name}</strong>.
      </p>
      <FormError message={error} />
      {status === "authenticated" ? (
        user?.email === inv.email ? (
          <Button className="w-full" onClick={accept} loading={busy}>
            Accept invitation
          </Button>
        ) : (
          <FormError message={`You are signed in as ${user?.email}. Sign in as ${inv.email} to accept.`} />
        )
      ) : (
        <div className="grid gap-2">
          <Button asChild>
            <Link href={`/register?next=${encodeURIComponent(here)}`}>Create an account to accept</Link>
          </Button>
          <Button asChild variant="outline">
            <Link href={`/login?next=${encodeURIComponent(here)}`}>I already have an account</Link>
          </Button>
        </div>
      )}
    </div>
  );
}

export default function AcceptInvitationPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>You have been invited</CardTitle>
        <CardDescription>Join your team on XploAds.</CardDescription>
      </CardHeader>
      <CardContent>
        <Suspense>
          <Accept />
        </Suspense>
      </CardContent>
    </Card>
  );
}
