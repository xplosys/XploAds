"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui/misc";
import { useAuditLogs, useMembers } from "@/features/organizations/api";
import { useCurrentOrg } from "@/hooks/use-org";
import { formatDateTime } from "@/lib/utils";
import { errorMessage } from "@/services/api-client";

export default function AuditPage() {
  const { orgId, can } = useCurrentOrg();
  const [offset, setOffset] = useState(0);
  const logs = useAuditLogs(orgId, offset);
  const members = useMembers(orgId);
  if (!can("audit.read")) return <EmptyState title="You do not have access to the audit log" />;
  const names = new Map(members.data?.map((m) => [m.user_id, m.full_name]));

  return (
    <>
      <PageHeader title="Audit log" description="An append-only record of security-relevant actions in this organization." />
      <Card>
        <CardContent className="p-0">
          {logs.isLoading ? (
            <Spinner />
          ) : logs.isError ? (
            <div className="p-6">
              <ErrorState message={errorMessage(logs.error)} onRetry={() => logs.refetch()} />
            </div>
          ) : !logs.data!.items.length ? (
            <div className="p-6">
              <EmptyState title="No activity yet" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-6 py-3 font-medium">When</th>
                    <th className="px-6 py-3 font-medium">Action</th>
                    <th className="px-6 py-3 font-medium">Actor</th>
                    <th className="px-6 py-3 font-medium">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.data!.items.map((l) => (
                    <tr key={l.id} className="border-b last:border-0 align-top">
                      <td className="whitespace-nowrap px-6 py-3 text-muted-foreground">{formatDateTime(l.occurred_at)}</td>
                      <td className="px-6 py-3 font-mono text-xs">{l.action}</td>
                      <td className="px-6 py-3">
                        {l.actor_user_id ? (names.get(l.actor_user_id) ?? "Former member / agency staff") : l.actor_type}
                      </td>
                      <td className="px-6 py-3 font-mono text-xs text-muted-foreground">
                        {Object.keys(l.metadata).length ? JSON.stringify(l.metadata) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
      {logs.data && logs.data.total > 25 && (
        <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {offset + 1}–{Math.min(offset + 25, logs.data.total)} of {logs.data.total}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(offset - 25)}>
              Previous
            </Button>
            <Button variant="outline" size="sm" disabled={offset + 25 >= logs.data.total} onClick={() => setOffset(offset + 25)}>
              Next
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
