"use client";

import { CheckCircle2, Download, FileText, Film, Loader2, Trash2, Type, UploadCloud, XCircle } from "lucide-react";
import { useParams } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog, Dialog } from "@/components/ui/dialog";
import { Field } from "@/components/ui/form";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { Badge, EmptyState, ErrorState, Spinner } from "@/components/ui/misc";
import {
  assetDownloadUrl,
  formatBytes,
  useAssetRules,
  useAssets,
  useDeleteAsset,
  useUpdateAsset,
  useUploadAsset,
} from "@/features/brands/api";
import { useCurrentOrg } from "@/hooks/use-org";
import { cn, formatDate } from "@/lib/utils";
import { errorMessage } from "@/services/api-client";
import type { Asset, AssetKind, RightsSource } from "@/types/api";

const KINDS: { value: AssetKind; label: string }[] = [
  { value: "logo", label: "Logo" },
  { value: "image", label: "Image" },
  { value: "video", label: "Video" },
  { value: "document", label: "Document" },
  { value: "font", label: "Font" },
];
const RIGHTS: { value: RightsSource; label: string }[] = [
  { value: "owned", label: "We own it" },
  { value: "licensed", label: "Licensed" },
  { value: "stock", label: "Stock" },
  { value: "user_generated", label: "Customer content (with permission)" },
  { value: "ai_generated", label: "AI generated" },
];

interface UploadRow {
  id: string;
  name: string;
  progress: number;
  state: "uploading" | "verifying" | "ready" | "rejected" | "failed";
  message?: string;
}

function guessKind(file: File): AssetKind {
  if (file.type.startsWith("video/")) return "video";
  if (file.type === "application/pdf") return "document";
  if (/\.(woff2?|ttf|otf)$/i.test(file.name)) return "font";
  return "image";
}

function Thumb({ a }: { a: Asset }) {
  if (a.url && a.mime_type?.startsWith("image/"))
    // eslint-disable-next-line @next/next/no-img-element -- signed storage URL
    return <img src={a.url} alt={a.alt_text ?? ""} className="h-full w-full object-contain" loading="lazy" />;
  const Icon = a.kind === "video" ? Film : a.kind === "font" ? Type : FileText;
  return <Icon className="size-10 text-muted-foreground" aria-hidden />;
}

export default function AssetsPage() {
  const { orgId, can } = useCurrentOrg();
  const { brandId } = useParams<{ brandId: string }>();
  const [filter, setFilter] = useState<AssetKind | undefined>();
  const assets = useAssets(orgId, brandId, filter);
  const rules = useAssetRules();
  const upload = useUploadAsset(orgId, brandId);
  const update = useUpdateAsset(orgId, brandId);
  const remove = useDeleteAsset(orgId, brandId);
  const [kind, setKind] = useState<AssetKind | "auto">("auto");
  const [rights, setRights] = useState<RightsSource>("owned");
  const [rows, setRows] = useState<UploadRow[]>([]);
  const [dragging, setDragging] = useState(false);
  const [selected, setSelected] = useState<Asset | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const manage = can("brands.manage");

  const patchRow = (id: string, patch: Partial<UploadRow>) => setRows((r) => r.map((x) => (x.id === id ? { ...x, ...patch } : x)));

  const handleFiles = async (files: FileList | File[]) => {
    for (const file of Array.from(files).slice(0, 20)) {
      const id = crypto.randomUUID();
      const k = kind === "auto" ? guessKind(file) : kind;
      setRows((r): UploadRow[] => [{ id, name: file.name, progress: 0, state: "uploading" as const }, ...r].slice(0, 20));
      const rule = rules.data?.find((r) => r.kind === k);
      const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
      if (rule && !rule.extensions.includes(ext)) {
        patchRow(id, { state: "failed", message: `Not allowed for ${k}. Use ${rule.extensions.join(", ")}.` });
        continue;
      }
      if (rule && file.size > rule.max_bytes) {
        patchRow(id, { state: "failed", message: `Larger than the ${formatBytes(rule.max_bytes)} limit for ${k}.` });
        continue;
      }
      try {
        const asset = await upload.mutateAsync({
          kind: k,
          file,
          rightsSource: rights,
          onProgress: (p) => patchRow(id, { progress: p, state: p >= 100 ? "verifying" : "uploading" }),
        });
        patchRow(id, asset.status === "ready"
          ? { state: "ready", progress: 100 }
          : { state: "rejected", message: asset.rejection_reason ?? "Rejected" });
      } catch (e) {
        patchRow(id, { state: "failed", message: errorMessage(e) });
      }
    }
  };

  const download = async (a: Asset) => {
    try {
      window.open(await assetDownloadUrl(orgId, a.id), "_blank", "noopener,noreferrer");
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  return (
    <div className="space-y-6">
      {manage && (
        <Card>
          <CardHeader>
            <CardTitle>Upload assets</CardTitle>
            <CardDescription>
              Files go straight to secure storage and are checked before use. PNG, JPG, WebP, GIF, MP4, MOV, WebM, PDF and web
              fonts are accepted; SVG is not, for security.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Asset type" htmlFor="up-kind">
                <NativeSelect id="up-kind" value={kind} onChange={(e) => setKind(e.target.value as AssetKind | "auto")}>
                  <option value="auto">Detect from file</option>
                  {KINDS.map((k) => (
                    <option key={k.value} value={k.value}>
                      {k.label}
                    </option>
                  ))}
                </NativeSelect>
              </Field>
              <Field label="Usage rights" htmlFor="up-rights" hint="Meta can reject ads that use content you have no rights to.">
                <NativeSelect id="up-rights" value={rights} onChange={(e) => setRights(e.target.value as RightsSource)}>
                  {RIGHTS.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </NativeSelect>
              </Field>
            </div>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                handleFiles(e.dataTransfer.files);
              }}
              className={cn(
                "flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-8 text-center text-sm",
                dragging ? "border-primary bg-primary/5" : "border-input",
              )}
            >
              <UploadCloud className="size-8 text-muted-foreground" aria-hidden />
              <p>Drag files here, or</p>
              <Button type="button" variant="outline" size="sm" onClick={() => inputRef.current?.click()}>
                Choose files
              </Button>
              <input
                ref={inputRef}
                type="file"
                multiple
                className="sr-only"
                aria-label="Choose files to upload"
                data-testid="asset-file-input"
                onChange={(e) => {
                  if (e.target.files) handleFiles(e.target.files);
                  e.target.value = "";
                }}
              />
            </div>
            {rows.length > 0 && (
              <ul className="space-y-2" aria-label="Uploads">
                {rows.map((r) => (
                  <li key={r.id} className="flex items-center gap-3 text-sm">
                    {r.state === "ready" ? (
                      <CheckCircle2 className="size-4 text-success" aria-label="Uploaded" />
                    ) : r.state === "rejected" || r.state === "failed" ? (
                      <XCircle className="size-4 text-destructive" aria-label="Failed" />
                    ) : (
                      <Loader2 className="size-4 animate-spin text-muted-foreground" aria-label="In progress" />
                    )}
                    <span className="truncate font-medium">{r.name}</span>
                    <span className="ml-auto shrink-0 text-xs text-muted-foreground">
                      {r.state === "uploading"
                        ? `${r.progress}%`
                        : r.state === "verifying"
                          ? "Checking file…"
                          : r.state === "ready"
                            ? "Ready"
                            : r.message}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter assets">
        {[{ value: undefined, label: "All" }, ...KINDS].map((k) => (
          <Button key={k.label} size="sm" variant={filter === k.value ? "secondary" : "ghost"} onClick={() => setFilter(k.value)}>
            {k.label}
          </Button>
        ))}
      </div>

      {assets.isLoading ? (
        <Spinner />
      ) : assets.isError ? (
        <ErrorState message={errorMessage(assets.error)} onRetry={() => assets.refetch()} />
      ) : !assets.data?.items.length ? (
        <EmptyState title="No assets yet" description="Upload logos, product photos, videos and brand fonts." />
      ) : (
        <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4" aria-label="Asset library">
          {assets.data.items.map((a) => (
            <li key={a.id}>
              <button
                type="button"
                onClick={() => setSelected(a)}
                className="block w-full overflow-hidden rounded-lg border bg-card text-left hover:shadow-md"
              >
                <div className="flex aspect-square items-center justify-center bg-muted/40 p-2">
                  <Thumb a={a} />
                </div>
                <div className="space-y-0.5 p-2">
                  <p className="truncate text-sm font-medium">{a.title || a.original_filename}</p>
                  <p className="text-xs capitalize text-muted-foreground">
                    {a.kind} · {formatBytes(a.size_bytes)}
                    {a.width ? ` · ${a.width}×${a.height}` : ""}
                  </p>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}

      {selected && (
        <AssetDialog
          asset={selected}
          manage={manage}
          saving={update.isPending}
          onClose={() => setSelected(null)}
          onDownload={() => download(selected)}
          onDelete={() => setConfirmDelete(true)}
          onSave={async (patch) => {
            try {
              const saved = await update.mutateAsync({ id: selected.id, ...patch });
              setSelected(saved);
              toast.success("Asset details saved");
            } catch (e) {
              toast.error(errorMessage(e));
            }
          }}
        />
      )}
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete this asset?"
        description="It is removed from storage and from any brand logo or product that uses it."
        confirmLabel="Delete asset"
        destructive
        loading={remove.isPending}
        onConfirm={async () => {
          try {
            await remove.mutateAsync(selected!.id);
            setConfirmDelete(false);
            setSelected(null);
          } catch (e) {
            toast.error(errorMessage(e));
          }
        }}
      />
    </div>
  );
}

function AssetDialog({
  asset,
  manage,
  saving,
  onClose,
  onSave,
  onDownload,
  onDelete,
}: {
  asset: Asset;
  manage: boolean;
  saving: boolean;
  onClose: () => void;
  onSave: (patch: Partial<Asset>) => void;
  onDownload: () => void;
  onDelete: () => void;
}) {
  const [title, setTitle] = useState(asset.title ?? "");
  const [alt, setAlt] = useState(asset.alt_text ?? "");
  const [tags, setTags] = useState(asset.tags.join(", "));
  const [rights, setRights] = useState<RightsSource>(asset.rights_source);
  const [notes, setNotes] = useState(asset.rights_notes ?? "");

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()} title={asset.title || asset.original_filename}>
      <div className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
        <div className="flex h-48 items-center justify-center rounded-md bg-muted/40">
          {asset.kind === "video" && asset.url ? (
            <video src={asset.url} controls className="max-h-48" />
          ) : (
            <Thumb a={asset} />
          )}
        </div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <dt>File</dt>
          <dd className="truncate">{asset.original_filename}</dd>
          <dt>Type</dt>
          <dd>{asset.mime_type}</dd>
          <dt>Size</dt>
          <dd>{formatBytes(asset.size_bytes)}</dd>
          {asset.width && (
            <>
              <dt>Dimensions</dt>
              <dd>
                {asset.width}×{asset.height}px
              </dd>
            </>
          )}
          <dt>Uploaded</dt>
          <dd>{formatDate(asset.created_at)}</dd>
        </dl>
        <fieldset disabled={!manage} className="space-y-3">
          <Field label="Title" htmlFor="a-title">
            <Input id="a-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />
          </Field>
          <Field label="Alt text" htmlFor="a-alt" hint="Describes the image for accessibility and AI context.">
            <Input id="a-alt" value={alt} onChange={(e) => setAlt(e.target.value)} maxLength={500} />
          </Field>
          <Field label="Tags" htmlFor="a-tags" hint="Comma separated">
            <Input id="a-tags" value={tags} onChange={(e) => setTags(e.target.value)} />
          </Field>
          <Field label="Usage rights" htmlFor="a-rights">
            <NativeSelect id="a-rights" value={rights} onChange={(e) => setRights(e.target.value as RightsSource)}>
              {RIGHTS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <Field label="Rights notes" htmlFor="a-notes" hint="Licence number, photographer, expiry terms.">
            <Textarea id="a-notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </Field>
        </fieldset>
        <div className="flex flex-wrap gap-2">
          {manage && (
            <Button
              loading={saving}
              onClick={() =>
                onSave({
                  title,
                  alt_text: alt,
                  tags: tags.split(",").map((t) => t.trim()).filter(Boolean).slice(0, 20),
                  rights_source: rights,
                  rights_notes: notes,
                })
              }
            >
              Save details
            </Button>
          )}
          <Button variant="outline" onClick={onDownload}>
            <Download /> Download
          </Button>
          {manage && (
            <Button variant="outline" onClick={onDelete} className="ml-auto text-destructive">
              <Trash2 /> Delete
            </Button>
          )}
        </div>
        <Badge variant="muted">{RIGHTS.find((r) => r.value === asset.rights_source)?.label}</Badge>
      </div>
    </Dialog>
  );
}
