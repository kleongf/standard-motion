import { expect, test } from "@playwright/test";

import { EPISODES, episodeId, ingest, referenceLabel } from "./helpers.ts";

// It releases inside the release height's margin, and it's never boxed, so it needs review on
// "never drops it" (release height near threshold, no exterior track; its wrist track is healthy)
// and on placement (no exterior track). Other specs' revealed Episodes share the queue, so this
// asserts on its own Episode only (the queue's order is covered by the backend's review tests).
const [UNSURE] = EPISODES.review;
const ID = episodeId(UNSURE);
const NEVER_DROPS = "never drops it";
const PLACES = "places it in or on the target named in the instruction";

test.beforeEach(async ({ request }) => {
  await ingest(request, EPISODES.review);
  await referenceLabel(request, [ID]);
});

test("answering an Episode's unsure Phrase takes it out of the queue", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  // ?episode= opens an Episode only while it's in the queue.
  await page.goto(`/?page=review&episode=${encodeURIComponent(ID)}`);

  const current = page.getByTestId("review-current");
  await expect(current).toContainText(ID);
  const yourCall = page.getByRole("region", { name: "Your call" });
  await expect(yourCall.getByRole("group")).toHaveText([
    new RegExp(`${NEVER_DROPS}.*near threshold`),
    new RegExp(PLACES),
  ]);
  await page.keyboard.press("2"); // Fail, on the focused (first) unsure Phrase: a hard fail decides

  await expect(current.filter({ hasText: ID })).toHaveCount(0);
  const upNext = page.getByRole("region", { name: "Up next" });
  await expect(upNext.getByRole("button", { name: new RegExp(ID) })).toHaveCount(0);
  await page.goto(`/?page=episodes&episode=${encodeURIComponent(ID)}`);
  await expect(page.getByTestId("reason")).toHaveText(
    `Rejected: "${NEVER_DROPS}" was marked fail in review.`,
  );
  expect(errors).toEqual([]);
});
