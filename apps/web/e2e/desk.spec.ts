import { expect, test } from "@playwright/test";

test("step-therapy demo reaches the desk and can be approved", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("ClaimSight")).toBeVisible();
  await page.getByRole("button", { name: "Step-therapy demo" }).click();
  await expect(page.getByRole("heading", { name: "CLM-GLP1-2026" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.locator(".rec em")).toHaveText(/approve/i);
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.locator(".qstat").first()).toContainText(/approved/i, {
    timeout: 15_000,
  });
});
