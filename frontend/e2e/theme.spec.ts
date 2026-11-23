import { expect, test } from "@playwright/test";

test("dark mode: one toggle button, persists across reload, defaults to the system setting", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/login");
  const html = page.locator("html");
  const toDark = page.getByRole("button", { name: "Switch to dark mode" }).filter({ visible: true });
  const toLight = page.getByRole("button", { name: "Switch to light mode" }).filter({ visible: true });

  // follows the OS until the user chooses
  await expect(html).not.toHaveClass(/dark/);
  await expect(toDark).toBeVisible();
  await expect(toLight).toHaveCount(0);
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(html).toHaveClass(/dark/);
  await expect(toLight).toBeVisible();

  // explicit choice wins over the OS and survives a reload
  await toLight.click();
  await expect(html).not.toHaveClass(/dark/);
  await page.reload();
  await expect(html).not.toHaveClass(/dark/);
  await toDark.click();
  await expect(html).toHaveClass(/dark/);
  await page.emulateMedia({ colorScheme: "light" });
  await page.reload();
  await expect(html).toHaveClass(/dark/);
  await expect(toLight).toBeVisible();
  await expect(toDark).toHaveCount(0);
});
