import { expect, test } from "@playwright/test";

import { EPISODES } from "./helpers.ts";

test("ingesting Episodes shows progress, then the new counts", async ({ page, request }) => {
  const before = ((await (await request.get("/api/dataset")).json()) as { episodes: number })
    .episodes;
  await page.goto("/?page=prepare");

  await page.getByLabel("Ingest from droid_100").fill(EPISODES.prepare.join(" "));
  await page.getByRole("button", { name: "Ingest" }).click();

  await expect(page.getByTestId("job-progress")).toContainText("Last ingest", { timeout: 30_000 });
  // Per Episode: ingest, then the Spark-alone baseline and the wrist track (replayed).
  await expect(page.getByTestId("job-progress")).toContainText("6 of 6");
  await expect(page.getByTestId("episodes-ingested")).toContainText(String(before + 2));
  await expect(page.getByText(`droid_100 ${String(before + 2)}`)).toBeVisible();
});

test("an index that can't be read is named, and nothing starts", async ({ page }) => {
  await page.goto("/?page=prepare");

  await page.getByLabel("Ingest from droid_100").fill(`${String(EPISODES.prepare[0])} ep16`);
  await page.getByRole("button", { name: "Ingest" }).click();

  await expect(page.getByRole("alert")).toHaveText('Can\'t read "ep16"');
});
