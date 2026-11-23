"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, X } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useFieldArray, useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FormError } from "@/components/ui/form";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { useAssets, useBrand, useUpdateBrand } from "@/features/brands/api";
import { useCurrentOrg } from "@/hooks/use-org";
import { errorMessage } from "@/services/api-client";
import { SOCIAL_PLATFORMS, type Brand } from "@/types/api";

const url = z.union([z.url("Enter a full URL, e.g. https://example.com"), z.literal("")]);
const schema = z.object({
  name: z.string().trim().min(2, "Enter the brand name").max(200),
  tagline: z.string().max(300),
  industry: z.string().max(100),
  website: url,
  description: z.string().max(5000),
  tone_of_voice: z.string().max(3000),
  target_audience: z.string().max(3000),
  value_propositions: z.array(z.object({ value: z.string().trim().min(1, "Enter a value or remove the row").max(300) })).max(20),
  colors: z
    .array(
      z.object({
        name: z.string().trim().min(1, "Name the colour").max(60),
        hex: z.string().regex(/^#[0-9A-Fa-f]{6}$/, "Use a hex colour like #0AA3A3"),
        usage: z.enum(["primary", "secondary", "accent", "neutral", "background", "text"]),
      }),
    )
    .max(12),
  fonts: z
    .array(z.object({ family: z.string().trim().min(1, "Enter the font family").max(100), usage: z.enum(["heading", "body", "accent"]) }))
    .max(6),
  social: z.object(Object.fromEntries(SOCIAL_PLATFORMS.map((p) => [p, url])) as Record<(typeof SOCIAL_PLATFORMS)[number], typeof url>),
  logo_asset_id: z.string(),
  archived: z.boolean(),
});
type FormValues = z.infer<typeof schema>;

function toForm(b: Brand): FormValues {
  return {
    name: b.name,
    tagline: b.tagline ?? "",
    industry: b.industry ?? "",
    website: b.website ?? "",
    description: b.description ?? "",
    tone_of_voice: b.tone_of_voice ?? "",
    target_audience: b.target_audience ?? "",
    value_propositions: b.value_propositions.map((value) => ({ value })),
    colors: b.colors.map((c) => ({ ...c })),
    fonts: b.fonts.map((f) => ({ family: f.family, usage: f.usage })),
    social: Object.fromEntries(SOCIAL_PLATFORMS.map((p) => [p, b.social_links[p] ?? ""])) as FormValues["social"],
    logo_asset_id: b.logo_asset_id ?? "",
    archived: b.status === "archived",
  };
}

const PLATFORM_LABEL: Record<string, string> = {
  facebook: "Facebook", instagram: "Instagram", linkedin: "LinkedIn", x: "X (Twitter)", youtube: "YouTube",
  tiktok: "TikTok", whatsapp: "WhatsApp (wa.me link)", website: "Other website",
};

export default function BrandProfilePage() {
  const { orgId, can } = useCurrentOrg();
  const { brandId } = useParams<{ brandId: string }>();
  const brand = useBrand(orgId, brandId);
  const logos = useAssets(orgId, brandId);
  const update = useUpdateBrand(orgId, brandId);
  const [error, setError] = useState<string | null>(null);
  const editable = can("brands.manage");
  const form = useForm<FormValues>({ resolver: zodResolver(schema) });
  const vp = useFieldArray({ control: form.control, name: "value_propositions" });
  const colors = useFieldArray({ control: form.control, name: "colors" });
  const fonts = useFieldArray({ control: form.control, name: "fonts" });
  const colorValues = useWatch({ control: form.control, name: "colors" });

  useEffect(() => {
    if (brand.data) form.reset(toForm(brand.data));
  }, [brand.data, form]);

  if (!brand.data) return null;
  const errors = form.formState.errors;
  const logoChoices = (logos.data?.items ?? []).filter((a) => a.kind === "logo" || a.kind === "image");

  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await update.mutateAsync({
        name: v.name,
        tagline: v.tagline,
        industry: v.industry,
        website: v.website || null,
        description: v.description,
        tone_of_voice: v.tone_of_voice,
        target_audience: v.target_audience,
        value_propositions: v.value_propositions.map((x) => x.value),
        colors: v.colors,
        fonts: v.fonts,
        social_links: Object.fromEntries(Object.entries(v.social).filter(([, u]) => u)),
        logo_asset_id: v.logo_asset_id || null,
        status: v.archived ? "archived" : "active",
      });
      toast.success("Brand profile saved");
    } catch (e) {
      setError(errorMessage(e));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-6">
      <FormError message={error} />
      <fieldset disabled={!editable} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Identity</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Brand name" htmlFor="name" error={errors.name?.message}>
                <Input id="name" {...form.register("name")} />
              </Field>
              <Field label="Tagline" htmlFor="tagline" error={errors.tagline?.message}>
                <Input id="tagline" {...form.register("tagline")} />
              </Field>
              <Field label="Industry" htmlFor="industry">
                <Input id="industry" {...form.register("industry")} />
              </Field>
              <Field label="Website" htmlFor="website" error={errors.website?.message}>
                <Input id="website" placeholder="https://" {...form.register("website")} />
              </Field>
            </div>
            <Field label="About the business" htmlFor="description" hint="What you sell, where, and what makes you different.">
              <Textarea id="description" rows={4} {...form.register("description")} />
            </Field>
            <Field
              label="Logo"
              htmlFor="logo"
              hint={
                logoChoices.length ? undefined : (
                  <>
                    Upload a logo in <Link className="text-primary hover:underline" href={`/app/${orgId}/brands/${brandId}/assets`}>Assets</Link> first.
                  </>
                )
              }
            >
              <NativeSelect id="logo" {...form.register("logo_asset_id")}>
                <option value="">No logo</option>
                {logoChoices.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.title || a.original_filename} ({a.kind})
                  </option>
                ))}
              </NativeSelect>
            </Field>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Voice & audience</CardTitle>
            <CardDescription>The AI copywriter follows this exactly, so be specific.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Tone of voice" htmlFor="tone" hint="e.g. Warm and reassuring; plain English; no medical jargon.">
              <Textarea id="tone" rows={3} {...form.register("tone_of_voice")} />
            </Field>
            <Field label="Target audience" htmlFor="audience" hint="Who buys, their age, location, needs and objections.">
              <Textarea id="audience" rows={3} {...form.register("target_audience")} />
            </Field>
            <div className="space-y-2">
              <p className="text-sm font-medium">Value propositions</p>
              {vp.fields.map((f, i) => (
                <div key={f.id} className="flex gap-2">
                  <Input aria-label={`Value proposition ${i + 1}`} {...form.register(`value_propositions.${i}.value`)} />
                  <Button type="button" variant="ghost" size="icon" onClick={() => vp.remove(i)} aria-label="Remove">
                    <X />
                  </Button>
                </div>
              ))}
              {errors.value_propositions && <p className="text-xs text-destructive">Fill in or remove empty rows.</p>}
              {vp.fields.length < 20 && (
                <Button type="button" variant="outline" size="sm" onClick={() => vp.append({ value: "" })}>
                  <Plus /> Add value proposition
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Colours & fonts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              {colors.fields.map((f, i) => (
                <div key={f.id} className="grid grid-cols-[auto_1fr_8rem_9rem_auto] items-center gap-2">
                  <input
                    type="color"
                    aria-label="Pick colour"
                    className="size-9 cursor-pointer rounded border bg-transparent"
                    value={/^#[0-9A-Fa-f]{6}$/.test(colorValues?.[i]?.hex ?? "") ? colorValues[i].hex : "#000000"}
                    onChange={(e) => form.setValue(`colors.${i}.hex`, e.target.value.toUpperCase(), { shouldDirty: true })}
                  />
                  <Input aria-label="Colour name" placeholder="Name" {...form.register(`colors.${i}.name`)} />
                  <Input aria-label="Hex value" {...form.register(`colors.${i}.hex`)} />
                  <NativeSelect aria-label="Colour usage" {...form.register(`colors.${i}.usage`)}>
                    {["primary", "secondary", "accent", "neutral", "background", "text"].map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ))}
                  </NativeSelect>
                  <Button type="button" variant="ghost" size="icon" onClick={() => colors.remove(i)} aria-label="Remove colour">
                    <X />
                  </Button>
                </div>
              ))}
              {errors.colors && <p className="text-xs text-destructive">Each colour needs a name and a hex value like #0AA3A3.</p>}
              {colors.fields.length < 12 && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => colors.append({ name: "", hex: "#0AA3A3", usage: colors.fields.length ? "secondary" : "primary" })}
                >
                  <Plus /> Add colour
                </Button>
              )}
            </div>
            <div className="space-y-2">
              {fonts.fields.map((f, i) => (
                <div key={f.id} className="grid grid-cols-[1fr_9rem_auto] items-center gap-2">
                  <Input aria-label="Font family" placeholder="Font family, e.g. Inter" {...form.register(`fonts.${i}.family`)} />
                  <NativeSelect aria-label="Font usage" {...form.register(`fonts.${i}.usage`)}>
                    <option value="heading">heading</option>
                    <option value="body">body</option>
                    <option value="accent">accent</option>
                  </NativeSelect>
                  <Button type="button" variant="ghost" size="icon" onClick={() => fonts.remove(i)} aria-label="Remove font">
                    <X />
                  </Button>
                </div>
              ))}
              {fonts.fields.length < 6 && (
                <Button type="button" variant="outline" size="sm" onClick={() => fonts.append({ family: "", usage: fonts.fields.length ? "body" : "heading" })}>
                  <Plus /> Add font
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Social profiles</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            {SOCIAL_PLATFORMS.map((p) => (
              <Field key={p} label={PLATFORM_LABEL[p]} htmlFor={`social-${p}`} error={errors.social?.[p]?.message}>
                <Input id={`social-${p}`} placeholder="https://" {...form.register(`social.${p}`)} />
              </Field>
            ))}
          </CardContent>
        </Card>

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...form.register("archived")} /> Archived (hidden from new creatives and campaigns)
        </label>
      </fieldset>
      {editable ? (
        <Button type="submit" loading={form.formState.isSubmitting}>
          Save brand profile
        </Button>
      ) : (
        <p className="text-sm text-muted-foreground">You have read-only access to this brand.</p>
      )}
    </form>
  );
}
