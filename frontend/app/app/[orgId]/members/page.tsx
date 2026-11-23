"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { UserPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog, Dialog } from "@/components/ui/dialog";
import { Field, FormError } from "@/components/ui/form";
import { Input, NativeSelect } from "@/components/ui/input";
import { Badge, EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui/misc";
import { useAuth } from "@/features/auth/auth-provider";
import {
  useInvitations,
  useInvite,
  useMembers,
  useRemoveMember,
  useRevokeInvitation,
  useRoles,
  useSetMemberRole,
} from "@/features/organizations/api";
import { useCurrentOrg } from "@/hooks/use-org";
import { formatDate } from "@/lib/utils";
import { errorMessage } from "@/services/api-client";
import type { Member } from "@/types/api";

const inviteSchema = z.object({ email: z.email("Enter a valid email"), role_key: z.string().min(1) });

function InviteDialog({ orgId, open, onOpenChange }: { orgId: string; open: boolean; onOpenChange: (o: boolean) => void }) {
  const roles = useRoles(orgId);
  const invite = useInvite(orgId);
  const [error, setError] = useState<string | null>(null);
  const form = useForm({ resolver: zodResolver(inviteSchema), defaultValues: { email: "", role_key: "member" } });
  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await invite.mutateAsync(v);
      toast.success(`Invitation sent to ${v.email}`);
      form.reset();
      onOpenChange(false);
    } catch (e) {
      setError(errorMessage(e));
    }
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Invite a teammate" description="They will receive an email link that expires in 7 days.">
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <FormError message={error} />
        <Field label="Email" htmlFor="invite-email" error={form.formState.errors.email?.message}>
          <Input id="invite-email" type="email" {...form.register("email")} />
        </Field>
        <Field label="Role" htmlFor="invite-role">
          <NativeSelect id="invite-role" {...form.register("role_key")}>
            {roles.data?.map((r) => (
              <option key={r.id} value={r.key}>
                {r.name}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
          Send invitation
        </Button>
      </form>
    </Dialog>
  );
}

export default function MembersPage() {
  const { orgId, can } = useCurrentOrg();
  const { user } = useAuth();
  const members = useMembers(orgId);
  const invitations = useInvitations(orgId);
  const roles = useRoles(orgId);
  const setRole = useSetMemberRole(orgId);
  const remove = useRemoveMember(orgId);
  const revoke = useRevokeInvitation(orgId);
  const router = useRouter();
  const [inviting, setInviting] = useState(false);
  const [removing, setRemoving] = useState<Member | null>(null);
  const manage = can("members.manage");

  const changeRole = async (m: Member, roleKey: string) => {
    try {
      await setRole.mutateAsync({ membershipId: m.membership_id, roleKey });
      toast.success(`${m.full_name} is now ${roles.data?.find((r) => r.key === roleKey)?.name ?? roleKey}`);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  return (
    <>
      <PageHeader
        title="Team"
        description="People with access to this organization and what they can do."
        actions={
          can("members.invite") && (
            <Button onClick={() => setInviting(true)}>
              <UserPlus /> Invite
            </Button>
          )
        }
      />
      <Card>
        <CardContent className="p-0">
          {members.isLoading ? (
            <Spinner />
          ) : members.isError ? (
            <div className="p-6">
              <ErrorState message={errorMessage(members.error)} onRetry={() => members.refetch()} />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-6 py-3 font-medium">Member</th>
                    <th className="px-6 py-3 font-medium">Role</th>
                    <th className="px-6 py-3 font-medium">Joined</th>
                    <th className="px-6 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {members.data!.map((m) => {
                    const role = m.roles.find((r) => !r.workspace_id)?.role_key ?? "";
                    return (
                      <tr key={m.membership_id} className="border-b last:border-0">
                        <td className="px-6 py-3">
                          <p className="font-medium">
                            {m.full_name} {m.user_id === user?.id && <Badge variant="muted">You</Badge>}
                          </p>
                          <p className="text-muted-foreground">{m.email}</p>
                        </td>
                        <td className="px-6 py-3">
                          {manage ? (
                            <NativeSelect
                              aria-label={`Role for ${m.full_name}`}
                              className="h-9 w-44"
                              value={role}
                              disabled={setRole.isPending}
                              onChange={(e) => changeRole(m, e.target.value)}
                            >
                              {roles.data?.map((r) => (
                                <option key={r.id} value={r.key}>
                                  {r.name}
                                </option>
                              ))}
                            </NativeSelect>
                          ) : (
                            <Badge className="capitalize">{role.replace("_", " ")}</Badge>
                          )}
                        </td>
                        <td className="px-6 py-3 text-muted-foreground">{formatDate(m.joined_at)}</td>
                        <td className="px-6 py-3 text-right">
                          {(manage || m.user_id === user?.id) && (
                            <Button variant="ghost" size="sm" onClick={() => setRemoving(m)}>
                              {m.user_id === user?.id ? "Leave" : "Remove"}
                            </Button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {can("members.read") && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>Invitations</CardTitle>
          </CardHeader>
          <CardContent>
            {invitations.isLoading ? (
              <Spinner />
            ) : !invitations.data?.length ? (
              <EmptyState title="No invitations yet" description="Invite teammates to collaborate on campaigns and leads." />
            ) : (
              <ul className="divide-y">
                {invitations.data.map((i) => (
                  <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                    <div>
                      <p className="font-medium">{i.email}</p>
                      <p className="text-muted-foreground">
                        {i.role_key} · sent {formatDate(i.created_at)} · expires {formatDate(i.expires_at)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={i.status === "pending" ? "warning" : i.status === "accepted" ? "success" : "muted"}>
                        {i.status}
                      </Badge>
                      {i.status === "pending" && can("members.invite") && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            revoke.mutate(i.id, {
                              onSuccess: () => toast.success("Invitation revoked"),
                              onError: (e) => toast.error(errorMessage(e)),
                            })
                          }
                        >
                          Revoke
                        </Button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      <InviteDialog orgId={orgId} open={inviting} onOpenChange={setInviting} />
      <ConfirmDialog
        open={!!removing}
        onOpenChange={(o) => !o && setRemoving(null)}
        title={removing?.user_id === user?.id ? "Leave this organization?" : `Remove ${removing?.full_name}?`}
        description="They will immediately lose access to this organization's data."
        confirmLabel={removing?.user_id === user?.id ? "Leave" : "Remove"}
        destructive
        loading={remove.isPending}
        onConfirm={() =>
          removing &&
          remove.mutate(removing.membership_id, {
            onSuccess: () => {
              toast.success("Member removed");
              if (removing.user_id === user?.id) router.replace("/app");
              setRemoving(null);
            },
            onError: (e) => {
              toast.error(errorMessage(e));
              setRemoving(null);
            },
          })
        }
      />
    </>
  );
}
