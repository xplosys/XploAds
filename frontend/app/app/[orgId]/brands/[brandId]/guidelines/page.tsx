"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmDialog, Dialog } from "@/components/ui/dialog";
import { Field, FormError } from "@/components/ui/form";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { Badge, EmptyState, ErrorState, Spinner } from "@/components/ui/misc";
import { useDeleteGuideline, useGuidelines, useSaveGuideline } from "@/features/brands/api";
import { useCurrentOrg } from "@/hooks/use-org";
import { errorMessage } from "@/services/api-client";
import { GUIDELINE_CATEGORIES, type Guideline } from "@/types/api";

const CATEGORY_LABEL: Record<string, string> = {
  voice: "Voice", visual: "Visual", messaging: "Messaging", do: "Do", dont: "Don't", legal: "Legal", other: "Other",
};

const schema = z.object({
  category: z.enum(GUIDELINE_CATEGORIES),
  title: z.string().trim().min(1, "Add a short title").max(200),
  content: z.string().trim().min(1, "Describe the rule").max(5000),
  sort_order: z.coerce.number<number>().int().min(0).max(10000),
});

export default function GuidelinesPage() {
  const { orgId, can } = useCurrentOrg();
  const { brandId } = useParams<{ brandId: string }>();
  const list = useGuidelines(orgId, brandId);
  const save = useSaveGuideline(orgId, brandId);
  const remove = useDeleteGuideline(orgId, brandId);
  const [editing, setEditing] = useState<Guideline | "new" | null>(null);
  const [deleting, setDeleting] = useState<Guideline | null>(null);
  const [error, setError] = useState<string | null>(null);
  const form = useForm({ resolver: zodResolver(schema) });
  const manage = can("brands.manage");

  const openEditor = (g: Guideline | "new") => {
    setError(null);
    form.reset(
      g === "new"
        ? { category: "voice", title: "", content: "", sort_order: (list.data?.length ?? 0) * 10 }
        : { category: g.category, title: g.title, content: g.content, sort_order: g.sort_order },
    );
    setEditing(g);
  };

  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await save.mutateAsync({ ...v, id: editing && editing !== "new" ? editing.id : undefined });
      toast.success("Guideline saved");
      setEditing(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  });

  return (
    <>
      <div className="mb-4 flex items-center justify-between gap-4">
        <p className="text-sm text-muted-foreground">Rules every creative must follow: voice, visuals, claims and legal lines.</p>
        {manage && (
          <Button onClick={() => openEditor("new")}>
            <Plus /> Add guideline
          </Button>
        )}
      </div>
      {list.isLoading ? (
        <Spinner />
      ) : list.isError ? (
        <ErrorState message={errorMessage(list.error)} onRetry={() => list.refetch()} />
      ) : !list.data?.length ? (
        <EmptyState title="No guidelines yet" description="Add do's and don'ts, mandatory disclaimers and visual rules." />
      ) : (
        <div className="space-y-3">
          {list.data.map((g) => (
            <Card key={g.id}>
              <CardContent className="flex items-start justify-between gap-4 pt-6">
                <div className="space-y-1">
                  <p className="flex items-center gap-2 font-medium">
                    <Badge variant={g.category === "dont" ? "destructive" : g.category === "do" ? "success" : "muted"}>
                      {CATEGORY_LABEL[g.category]}
                    </Badge>
                    <span>{g.title}</span>
                  </p>
                  <p className="whitespace-pre-line text-sm text-muted-foreground">{g.content}</p>
                </div>
                {manage && (
                  <div className="flex shrink-0 gap-1">
                    <Button variant="ghost" size="icon" onClick={() => openEditor(g)} aria-label={`Edit ${g.title}`}>
                      <Pencil />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => setDeleting(g)} aria-label={`Delete ${g.title}`}>
                      <Trash2 />
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)} title={editing === "new" ? "Add guideline" : "Edit guideline"}>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <FormError message={error} />
          <div className="grid grid-cols-[1fr_6rem] gap-3">
            <Field label="Category" htmlFor="g-category">
              <NativeSelect id="g-category" {...form.register("category")}>
                {GUIDELINE_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {CATEGORY_LABEL[c]}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <Field label="Order" htmlFor="g-order">
              <Input id="g-order" type="number" min={0} {...form.register("sort_order")} />
            </Field>
          </div>
          <Field label="Title" htmlFor="g-title" error={form.formState.errors.title?.message}>
            <Input id="g-title" {...form.register("title")} />
          </Field>
          <Field label="Rule" htmlFor="g-content" error={form.formState.errors.content?.message}>
            <Textarea id="g-content" rows={5} {...form.register("content")} />
          </Field>
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
            Save guideline
          </Button>
        </form>
      </Dialog>
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="Delete this guideline?"
        description={deleting?.title ?? ""}
        confirmLabel="Delete"
        destructive
        loading={remove.isPending}
        onConfirm={async () => {
          try {
            await remove.mutateAsync(deleting!.id);
            setDeleting(null);
          } catch (e) {
            toast.error(errorMessage(e));
          }
        }}
      />
    </>
  );
}
