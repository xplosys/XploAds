"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { ErrorState, Spinner } from "@/components/ui/misc";
import { RequireAuth } from "@/features/auth/guards";
import { useOrganizations } from "@/features/organizations/api";
import { errorMessage } from "@/services/api-client";

function PickOrganization() {
  const router = useRouter();
  const orgs = useOrganizations();
  useEffect(() => {
    if (!orgs.data) return;
    if (orgs.data.length === 0) return router.replace("/onboarding");
    const saved = window.localStorage.getItem("xploads.activeOrg");
    const target = orgs.data.find((o) => o.id === saved) ?? orgs.data.find((o) => o.access === "member") ?? orgs.data[0];
    router.replace(`/app/${target.id}`);
  }, [orgs.data, router]);
  if (orgs.isError) return <ErrorState message={errorMessage(orgs.error)} onRetry={() => orgs.refetch()} />;
  return <Spinner label="Opening your workspace" />;
}

export default function AppIndex() {
  return (
    <RequireAuth>
      <PickOrganization />
    </RequireAuth>
  );
}
