import { Suspense } from "react";

import { AppShell } from "@/components/app-shell";
import { Spinner } from "@/components/ui/misc";
import { RequireAuth } from "@/features/auth/guards";

export default function OrgLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<Spinner />}>
      <RequireAuth>
        <AppShell>{children}</AppShell>
      </RequireAuth>
    </Suspense>
  );
}
