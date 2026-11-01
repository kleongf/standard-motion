import { expect, test } from "@playwright/test";

test("app loads and reaches the backend", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Pick-and-place · Prepare" })).toBeVisible();
  await expect(page.getByTestId("health-status")).toContainText("Backend ok");
  expect(errors).toEqual([]);
});

test("each page is reachable from the sidebar and kept in the URL", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Review" }).click();

  await expect(page.getByRole("heading", { name: "Review" })).toBeVisible();
  await expect(page).toHaveURL(/\?page=review$/);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Review" })).toBeVisible();
});

test("the Selection page explains how to draw a sample when there is none", async ({ page }) => {
  // e2e has no Meta API key, so no selection pass runs and there are no candidates.
  await page.goto("/?page=select");

  await expect(page.getByRole("heading", { name: "droid_1.0.1 selection" })).toBeVisible();
  await expect(page.getByText("winnow select droid_1.0.1 --size 300 --seed 0")).toBeVisible();
});

test("the theme toggle switches to dark and keeps it across a reload", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  await expect(page.locator("html")).not.toHaveClass(/\bdark\b/);

  await page
    .getByRole("radiogroup", { name: "Theme" })
    .getByRole("radio", { name: "Dark" })
    .click();

  await expect(page.locator("html")).toHaveClass(/\bdark\b/);
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/\bdark\b/);
});
