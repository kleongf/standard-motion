import { expect, test } from "@playwright/test";

import type { components } from "../frontend/src/api/schema.ts";
import { clickCompile, DEV_SET, episodeId, freezeDevSet, openDescription } from "./helpers.ts";

type DraftEdit = components["schemas"]["DraftEdit"];

// The frozen Description, whose compile against the Dev set is recorded.
const FROZEN =
  "Expert pick-and-place: grasps the object on the first try, never drops it, places it in or " +
  "on the target named in the instruction, no long pauses.";
const GRASP = "Grasp attempts, up to and including the grasp, ≤ 1";

// The sanity monitor reads the anchor pool, which is the Dev set: one Episode, the sets spec's,
// that grasps first time. It claims no Episode of its own: the Dev set is only read. Compiling
// restarts the draft that describe-edits and the other Describe specs share (clickCompile
// confirms starting afresh), which is safe because `workers: 1` runs the specs one at a time.
test("a Criterion that fails nothing warns, and the Episode only a Criterion rejects opens", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await freezeDevSet(request);
  await page.goto("/?page=describe");
  await openDescription(page);
  await page.getByLabel("Description", { exact: true }).fill(FROZEN);
  await clickCompile(page, request, FROZEN);

  // The one Episode passes the first-try Criterion: 0 of 1 fail is under 2%.
  const card = page.getByRole("article", { name: GRASP });
  await expect(card.getByTestId("fail-rate")).toHaveText(/^0 of 1 fail · 0% \(95% interval 0%–/);
  await expect(card.getByTestId("sanity-warning")).toHaveText("Rarely fails");
  await expect(card.getByTestId("sanity")).toContainText("Only 1 anchor Episode: too few to tell.");
  await expect(card.getByTestId("only-rejects")).toHaveCount(0);
  await expect(page.getByTestId("sanity-count")).toContainText("Rubric warning");

  // A threshold of 0 attempts, previewed and not saved, makes it the only reason the Episode is
  // Rejected: the server rescores the Dev set with and without it.
  const lowered: DraftEdit = { criteria: { "grasp-attempts": { threshold: 0 } } };
  await page.route("**/api/rubric/draft/preview", async (route) => {
    await route.continue({ postData: JSON.stringify(lowered) });
  });
  await page.reload();
  // The card is the draft's, still at ≤ 1; the preview is the lowered one.
  await expect(card.getByTestId("fail-rate")).toHaveText(/^1 of 1 fail · 100% /);
  await expect(card.getByTestId("sanity-warning")).toHaveText("Nearly always fails");
  await card.getByTestId("only-rejects").click();
  await page.getByRole("button", { name: episodeId(DEV_SET[0]) }).click();

  await expect(page).toHaveURL(
    new RegExp(`page=episodes.*episode=${encodeURIComponent(episodeId(DEV_SET[0]))}`),
  );
  expect(errors).toEqual([]);
});
