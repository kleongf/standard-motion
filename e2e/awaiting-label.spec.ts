import { expect, test } from "@playwright/test";

import { EPISODES, episodeId, ingest, referenceLabel } from "./helpers.ts";

const [INDEX] = EPISODES.awaitingLabel;
const EPISODE = episodeId(INDEX);
const ROW = new RegExp(`^${String(INDEX)} Move the black remote control`);

test("an Episode's outputs stay hidden until it has a Reference label", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await ingest(request, EPISODES.awaitingLabel);

  await page.goto("/?page=episodes");
  const row = page.getByRole("row", { name: ROW });
  await expect(row.getByTestId("awaiting-label")).toHaveText("Awaiting Reference label");
  await expect(row.getByTestId("triage-decision")).toHaveCount(0);
  await expect(page.getByText(/\d+ awaiting Reference label/)).toBeVisible();

  // Opened, it shows no Triage decision, Reason or lanes, and the API withholds them too.
  await row.click();
  await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toContainText(EPISODE);
  await expect(page.getByLabel("Triage").getByTestId("awaiting-label")).toBeVisible();
  await expect(page.getByTestId("triage-decision")).toHaveCount(0);
  await expect(page.getByTestId("reason")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Lane: / })).toHaveCount(0);
  const hidden = await request.get(`/api/episodes/${encodeURIComponent(EPISODE)}/triage`);
  expect(hidden.status()).toBe(403);
  const listed = (await (await request.get("/api/triage")).json()) as {
    rows: { episode_id: string }[];
  };
  expect(listed.rows.map((r) => r.episode_id)).not.toContain(EPISODE);

  // Once labelled, they appear.
  await referenceLabel(request, [EPISODE]);
  await page.reload();
  // Unboxed, its placement has no exterior track to check, so it needs review.
  await expect(page.getByTestId("triage-decision")).toHaveText("Needs review");
  await expect(page.getByTestId("reason")).not.toBeEmpty();
  await expect(page.getByRole("button", { name: /^Lane: Grasp attempts/ })).toBeVisible();
  await expect(page.getByTestId("awaiting-label")).toHaveCount(0);
  expect(errors).toEqual([]);
});
