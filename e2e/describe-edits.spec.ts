import { expect, test } from "@playwright/test";

import { clickCompile, freezeDevSet, openDescription } from "./helpers.ts";

// The frozen Description, whose compile against the Dev set is recorded.
const FROZEN =
  "Expert pick-and-place: grasps the object on the first try, never drops it, places it in or " +
  "on the target named in the instruction, no long pauses.";

test("dragging a threshold re-sorts the anchor pool, and the edit is kept", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  // One Dev set Episode, grasping first time. It's unboxed (compile's recording needs it so),
  // so its tracked Criteria are unsure and it needs review until a hard fail rejects it.
  await freezeDevSet(request);

  await page.goto("/?page=describe");
  await openDescription(page);
  await page.getByLabel("Description", { exact: true }).fill(FROZEN);
  await clickCompile(page, request, FROZEN);

  const card = page.getByRole("article", {
    name: "Grasp attempts, up to and including the grasp, ≤ 1",
  });
  const counts = card.getByTestId("anchor-counts");
  await expect(counts).toHaveText("Anchor pool: 1 pass · 0 fail · 0 unsure");
  await expect(page.getByTestId("anchor-sort")).toHaveText(
    "Sorts it: 0 Keep · 0 Reject · 1 Needs review",
  );
  await expect(
    page.getByRole("button", { name: /^Run v\d+ · \d+ assumptions unconfirmed$/ }),
  ).toBeVisible();

  // Drag the threshold to the left end: one attempt is now too many.
  const thumb = card.getByRole("slider");
  await thumb.scrollIntoViewIfNeeded();
  const track = await card.locator("[data-slot=slider]").boundingBox();
  const at = await thumb.boundingBox();
  if (!track || !at) throw new Error("the slider has no size");
  await page.mouse.move(at.x + at.width / 2, at.y + at.height / 2);
  await page.mouse.down();
  await page.mouse.move(track.x - 20, at.y + at.height / 2, { steps: 5 });
  await expect(counts).toHaveText("Anchor pool: 0 pass · 1 fail · 0 unsure");
  await expect(card.getByTestId("criterion-english")).toHaveText(
    "Grasp attempts, up to and including the grasp, ≤ 0",
  );
  await page.mouse.up();
  await expect(page.getByTestId("anchor-sort")).toHaveText(
    "Sorts it: 0 Keep · 1 Reject · 0 Needs review",
  );

  // Letting go saves it to the draft.
  const saved = page.getByRole("article", {
    name: "Grasp attempts, up to and including the grasp, ≤ 0",
  });
  await expect(saved).toBeVisible();
  await page.reload();
  await expect(saved.getByTestId("anchor-counts")).toHaveText(
    "Anchor pool: 0 pass · 1 fail · 0 unsure",
  );

  // Switched soft, it shows its counts but rejects nothing.
  await saved.getByRole("switch", { name: "Hard" }).click();
  await expect(saved).toContainText("soft · never rejects");
  await expect(page.getByTestId("anchor-sort")).toHaveText(
    "Sorts it: 0 Keep · 0 Reject · 1 Needs review",
  );
  expect(errors).toEqual([]);
});
