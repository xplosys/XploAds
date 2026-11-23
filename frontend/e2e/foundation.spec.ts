import { expect, test, type Page } from "@playwright/test";

const password = "E2e-Test-Passw0rd!";
// Next.js keeps recently visited routes mounted but hidden, so always target the visible copy.
const label = (page: Page, text: string) => page.getByLabel(text, { exact: true }).filter({ visible: true });
const button = (page: Page, name: string) => page.getByRole("button", { name, exact: true }).filter({ visible: true });
const link = (page: Page, name: string) => page.getByRole("link", { name, exact: true }).filter({ visible: true });
const text = (page: Page, value: string) => page.getByText(value, { exact: true }).filter({ visible: true });

test("register, create an agency, add a client, work inside it, sign out and back in", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;

  await page.goto("/register");
  await label(page, "Full name").fill("Riya Sharma");
  await label(page, "Work email").fill(email);
  await label(page, "Password").fill(password);
  await label(page, "Confirm password").fill(password);
  await button(page, "Create account").click();

  await expect(page).toHaveURL(/\/onboarding$/);
  await text(page, "Agency").click();
  await label(page, "Agency name").fill("Pixel Growth Agency");
  await button(page, "Create organization").click();

  await expect(page.getByRole("heading", { name: "Welcome, Riya" }).filter({ visible: true })).toBeVisible();
  await expect(text(page, "Verify your email address to invite teammates. Check your inbox for the link.")).toBeVisible();

  await link(page, "Clients").first().click();
  await button(page, "Add client").first().click();
  await label(page, "Client name").fill("Green Valley Realty");
  await page.getByRole("dialog").getByRole("button", { name: "Add client" }).click();
  await expect(text(page, "Green Valley Realty").first()).toBeVisible();
  await link(page, "Open").first().click();
  await expect(text(page, "Agency access")).toBeVisible();

  await link(page, "Workspaces").first().click();
  await button(page, "New workspace").click();
  await page.getByRole("dialog").getByLabel("Name").fill("Diwali Launch");
  await page.getByRole("dialog").getByRole("button", { name: "Create workspace" }).click();
  await expect(text(page, "Diwali Launch")).toBeVisible();

  await button(page, "Sign out").first().click();
  await expect(page).toHaveURL(/\/login/);
  await label(page, "Email").fill(email);
  await label(page, "Password").fill(password);
  await button(page, "Sign in").click();
  await expect(page).toHaveURL(/\/app\/[0-9a-f-]+/); // returns to where the user was

  // The session survives a full reload via the HttpOnly refresh cookie.
  await page.reload();
  await expect(link(page, "Dashboard").first()).toBeVisible();
});
