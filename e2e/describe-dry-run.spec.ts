import { expect, test, type Page } from "@playwright/test";

import { clickCompile, FROZEN, freezeDevSet } from "./helpers.ts";

// Compiling a Description with a visual Criterion asks Spark it on the anchor pool in the
// background (the dry run), and its pass rate shows on Describe without pressing Run. Like the
// other describe specs it claims no Episode: Describe reads only the Dev set, the sets spec's
// Episode 6, and the dry run's answers about it change nothing other specs assert on.

// Its compile is scripted with one Phrase holding a visual Criterion, and the dry run's three
// samples about Episode 6 all pass (backend/tests/record_dry_run.py).
const PLACED = "Neat place: leaves the block in the bowl.";

/** Type `text` into the Describe composer's Description box. */
async function writeDescription(page: Page, text: string): Promise<void> {
  await page.getByLabel("Description", { exact: true }).fill(text);
}

// Other specs compile the frozen Description and expect a recorded compile of it: leave it so.
test.afterEach(async ({ request }) => {
  const compiled = await request.post("/api/rubric/draft/compile", {
    data: { description: FROZEN, fresh: true },
  });
  expect(compiled.ok()).toBe(true);
});

test("a visual Criterion's pass rate on the anchor pool shows without pressing Run", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await freezeDevSet(request); // one Dev set Episode, which leaves the block in the bowl
  await page.goto("/?page=describe");

  // A wholly new Description compiles afresh, so the grasp settings are the seeded ones that the
  // dry run's scripted answers were asked under.
  await writeDescription(page, PLACED);
  await clickCompile(page, request, PLACED);

  const placed = page.getByRole("region", { name: "Phrase: leaves the block in the bowl" });
  const card = placed.getByRole("article");
  await expect(card).toContainText("ask_video");
  await expect(card.getByTestId("anchor-counts")).toHaveText(
    "Anchor pool: 1 pass · 0 fail · 0 unsure",
  );
  await expect(page.getByTestId("anchor-sort")).toHaveText(
    "Sorts it: 1 Keep · 0 Reject · 0 Needs review",
  );
  await expect(page.getByTestId("dry-run")).toBeHidden(); // done asking
  await expect(page.getByRole("button", { name: /^Run v/ })).toBeEnabled(); // never pressed
  expect(errors).toEqual([]);
});
