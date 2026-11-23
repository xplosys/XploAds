import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const password = "E2e-Test-Passw0rd!";
const fixtures = path.join(__dirname, "fixtures");
// Next.js keeps recently visited routes mounted but hidden, so always target the visible copy.
const label = (page: Page, text: string) => page.getByLabel(text, { exact: true }).filter({ visible: true });
const button = (page: Page, name: string) => page.getByRole("button", { name, exact: true }).filter({ visible: true });
const link = (page: Page, name: string) => page.getByRole("link", { name, exact: true }).filter({ visible: true });
const tab = (page: Page, name: string) =>
  page.getByRole("navigation", { name: "Brand sections" }).filter({ visible: true }).getByRole("link", { name: new RegExp(`^${name}`) });
const text = (page: Page, value: string) => page.getByText(value, { exact: true }).filter({ visible: true });

test("build a brand kit: profile, guideline, product, logo upload with verification", async ({ page }) => {
  await page.goto("/register");
  await label(page, "Full name").fill("Arjun Mehta");
  await label(page, "Work email").fill(`e2e-brand-${Date.now()}@example.com`);
  await label(page, "Password").fill(password);
  await label(page, "Confirm password").fill(password);
  await button(page, "Create account").click();
  await expect(page).toHaveURL(/\/onboarding$/);
  await label(page, "Organization name").fill("Smile Dental Clinic");
  await button(page, "Create organization").click();
  await expect(page.getByRole("heading", { name: "Welcome, Arjun" }).filter({ visible: true })).toBeVisible();

  // create brand
  await link(page, "Brands").first().click();
  await button(page, "Create your first brand").click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Brand name").fill("Smile Dental");
  await dialog.getByLabel("Tagline").fill("Gentle care for the whole family");
  await dialog.getByRole("button", { name: "Create brand" }).click();
  await expect(page.getByRole("heading", { name: /Smile Dental/ }).filter({ visible: true })).toBeVisible();
  await expect(text(page, "Default")).toBeVisible();

  // profile
  await label(page, "Tone of voice").fill("Warm, reassuring, plain English.");
  await button(page, "Add value proposition").click();
  await label(page, "Value proposition 1").fill("Same-day appointments");
  await button(page, "Add colour").click();
  await label(page, "Colour name").fill("Teal");
  await label(page, "Instagram").fill("https://instagram.com/smiledental");
  await button(page, "Save brand profile").click();
  await expect(text(page, "Brand profile saved")).toBeVisible();

  // guideline
  await tab(page, "Guidelines").click();
  await button(page, "Add guideline").click();
  await page.getByRole("dialog").getByLabel("Category").selectOption("dont");
  await page.getByRole("dialog").getByLabel("Title").fill("No before/after photos");
  await page.getByRole("dialog").getByLabel("Rule").fill("Meta health policy: never show before/after comparisons.");
  await page.getByRole("dialog").getByRole("button", { name: "Save guideline" }).click();
  await expect(text(page, "No before/after photos")).toBeVisible();

  // assets: a valid logo is accepted, a spoofed file is rejected by the server
  await tab(page, "Assets").click();
  await label(page, "Asset type").selectOption("logo");
  const input = label(page, "Choose files to upload");
  await input.setInputFiles(path.join(fixtures, "logo.png"));
  await expect(page.getByLabel("Uploads").filter({ visible: true }).getByText("Ready")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByLabel("Asset library").filter({ visible: true }).getByText("logo.png")).toBeVisible();
  await input.setInputFiles(path.join(fixtures, "not-an-image.png"));
  await expect(
    page.getByLabel("Uploads").filter({ visible: true }).getByText("The file content does not match an allowed type"),
  ).toBeVisible({ timeout: 20_000 });

  // the uploaded image is served back through a signed URL
  const thumb = page.getByLabel("Asset library").filter({ visible: true }).locator("img").first();
  await expect(thumb).toBeVisible();
  await expect.poll(() => thumb.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(240);

  // use it as the brand logo
  await tab(page, "Profile").click();
  await label(page, "Logo").selectOption({ label: "logo.png (logo)" });
  await button(page, "Save brand profile").click();
  await expect(page.getByRole("img", { name: "Smile Dental logo" }).filter({ visible: true })).toBeVisible();

  // product with a price
  await tab(page, "Products & services").click();
  await button(page, "Add product or service").click();
  const pd = page.getByRole("dialog");
  await pd.getByLabel("Type").selectOption("service");
  await pd.getByLabel("Name").fill("Teeth whitening");
  await pd.getByLabel("Price").fill("4999");
  await pd.getByLabel("Currency").selectOption("INR");
  await pd.getByLabel("Key benefits").fill("45 minutes\nTake-home kit");
  await pd.getByRole("button", { name: "Save" }).click();
  await expect(text(page, "Teeth whitening")).toBeVisible();
  await expect(page.getByText(/4,999/).filter({ visible: true })).toBeVisible();

  // dashboard step is ticked off
  await link(page, "Dashboard").first().click();
  await expect(text(page, "Create your brand kit")).toHaveClass(/line-through/);
});
