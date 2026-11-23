"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Field, FormError } from "@/components/ui/form";
import { Input, Textarea } from "@/components/ui/input";
import { Badge, ErrorState, PageHeader, Spinner } from "@/components/ui/misc";
import { useCreateWorkspace, useUpdateWorkspace, useWorkspaces } from "@/features/organizations/api";
import { useCurrentOrg } from "@/hooks/use-org";
import { formatDate } from "@/lib/utils";
import { errorMessage } from "@/services/api-client";

const schema = z.object({ name: z.string().trim().min(2, "Enter a name").max(200), description: z.string().max(2000).optional() });

export default function WorkspacesPage() {
  const { orgId, can } = useCurrentOrg();
  const workspaces = useWorkspaces(orgId);
  const create = useCreateWorkspace(orgId);
  const update = useUpdateWorkspace(orgId);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const form = useForm({ resolver: zodResolver(schema), defaultValues: { name: "", description: "" } });
  const manage = can("workspaces.manage");

  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await create.mutateAsync({ name: v.name, description: v.description || undefined });
      toast.success("Workspace created");
      form.reset();
      setOpen(false);
    } catch (e) {
      setError(errorMessage(e));
    }
  });

  return (
    <>
      <PageHeader
        title="Workspaces"
        description="Group campaigns and teams by department, region or brand."
        actions={
          manage && (
            <Button onClick={() => setOpen(true)}>
              <Plus /> New workspace
            </Button>
          )
        }
      />
      {workspaces.isLoading ? (
        <Spinner />
      ) : workspaces.isError ? (
        <ErrorState message={errorMessage(workspaces.error)} onRetry={() => workspaces.refetch()} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {workspaces.data!.map((w) => (
            <Card key={w.id} className={w.status === "archived" ? "opacity-60" : ""}>
              <CardContent className="space-y-2 pt-6">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold">{w.name}</p>
                  {w.is_default ? <Badge>Default</Badge> : w.status === "archived" && <Badge variant="muted">Archived</Badge>}
                </div>
                <p className="min-h-10 text-sm text-muted-foreground">{w.description || "No description"}</p>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Created {formatDate(w.created_at)}</span>
                  {manage && !w.is_default && (
                    <button
                      className="font-medium text-primary hover:underline"
                      onClick={() =>
                        update.mutate(
                          { workspaceId: w.id, status: w.status === "archived" ? "active" : "archived" },
                          { onError: (e) => toast.error(errorMessage(e)) },
                        )
                      }
                    >
                      {w.status === "archived" ? "Restore" : "Archive"}
                    </button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      <Dialog open={open} onOpenChange={setOpen} title="New workspace">
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <FormError message={error} />
          <Field label="Name" htmlFor="ws-name" error={form.formState.errors.name?.message}>
            <Input id="ws-name" {...form.register("name")} />
          </Field>
          <Field label="Description" htmlFor="ws-desc">
            <Textarea id="ws-desc" {...form.register("description")} />
          </Field>
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
            Create workspace
          </Button>
        </form>
      </Dialog>
    </>
  );
}
