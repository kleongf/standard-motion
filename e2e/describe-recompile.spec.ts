import { expect, test, type APIRequestContext } from "@playwright/test";

import { freezeDevSet, openDescription } from "./helpers.ts";

// The frozen Description, and the same with its grasp Phrase edited: both the compile and the
// recompile of the edit are recorded (backend/tests/record_meta.py, EDITED).
const FROZEN =
  "Expert pick-and-place: grasps the object on the first try, never drops it, places it in or " +
  "on the target named in the instruction, no long pauses.";
const EDITED = FROZEN.replace(
  "grasps the object on the first try",
  "grasps the object within two tries",
);
const PAUSES = "Longest stretch with the arm under 0.01 m/s < 1 s";

/** Compile the frozen Description afresh, whatever draft another spec left. */
async function compileFrozen(request: APIRequestContext): Promise<void> {
  const compiled = await request.post("/api/rubric/draft/compile", {
    data: { description: FROZEN, fresh: true },
  });
  expect(compiled.ok()).toBe(true);
}

// Other specs compile the frozen Description and expect a recorded compile of it: leave it so.
test.afterEach(async ({ request }) => {
  await compileFrozen(request);
});

test("editing a sentence recompiles only its Phrase, keeps the rest, and re-sorts", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await freezeDevSet(request); // one Dev set Episode, grasping first time
  await compileFrozen(request);
  // No attempt allowed: the anchor Episode is rejected on the grasp Phrase. The pauses go soft.
  const draft = (await (await request.get("/api/rubric/draft")).json()) as {
    criteria: { id: string; primitive: string }[];
  };
  const id = (primitive: string) => draft.criteria.find((c) => c.primitive === primitive)?.id ?? "";
  const edit = {
    [id("grasp_attempts")]: { threshold: 0 },
    [id("longest_still_s")]: { hard: false },
  };
  expect((await request.patch("/api/rubric/draft", { data: { criteria: edit } })).ok()).toBe(true);

  await page.goto("/?page=describe");
  const sort = page.getByTestId("anchor-sort");
  await expect(sort).toHaveText("Sorts it: 0 Keep · 1 Reject · 0 Needs review");
  const pauses = page.getByRole("article", { name: PAUSES });
  await expect(pauses).toContainText("soft · never rejects");

  // Hold the recompile: while Spark reads the edit, the Criterion cards can't be edited.
  let release = () => {};
  const held = new Promise<void>((resolve) => (release = resolve));
  await page.route("**/api/rubric/draft/compile", async (route) => {
    await held;
    await route.continue();
  });
  const hard = pauses.getByRole("switch", { name: "Hard" });
  await expect(hard).toBeEnabled();
  await openDescription(page);
  await page.getByLabel("Description", { exact: true }).fill(EDITED);
  await page.getByRole("button", { name: "Recompile changes" }).click();
  await expect(page.getByRole("button", { name: "Compiling…" })).toBeVisible();
  await expect(hard).toBeDisabled();
  release();

  await expect(page.getByTestId("recompile-note")).toHaveText(
    "Recompiled only “grasps the object within two tries”; kept 4 unchanged Phrases with " +
      "their Criteria and labels.",
  );
  await expect(
    page.getByRole("article", { name: "Grasp attempts, up to and including the grasp, ≤ 2" }),
  ).toBeVisible();
  await expect(sort).toHaveText("Sorts it: 0 Keep · 0 Reject · 1 Needs review");
  await expect(pauses).toContainText("soft · never rejects"); // a kept Criterion keeps its edit
  await expect(hard).toBeEnabled();
  // The Description is the draft's own again: compiling it would start afresh, so it asks first.
  await openDescription(page);
  await page.getByRole("button", { name: "Compile", exact: true }).click();
  const confirm = page.getByRole("alertdialog", { name: "Start the draft afresh?" });
  await expect(confirm).toBeVisible();
  await confirm.getByRole("button", { name: "Keep the draft" }).click();
  await expect(confirm).toBeHidden();
  await expect(page.getByTestId("recompile-note")).toBeVisible(); // nothing compiled
  expect(errors).toEqual([]);
});

test("compiling the unchanged Description starts afresh only once confirmed", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await freezeDevSet(request);
  await compileFrozen(request);
  const grasps = async () => {
    const draft = (await (await request.get("/api/rubric/draft")).json()) as {
      criteria: { id: string; primitive: string; threshold: number }[];
    };
    return draft.criteria.find((c) => c.primitive === "grasp_attempts");
  };
  const id = (await grasps())?.id ?? "";
  const edit = { criteria: { [id]: { threshold: 0 } } };
  expect((await request.patch("/api/rubric/draft", { data: edit })).ok()).toBe(true);

  await page.goto("/?page=describe");
  await openDescription(page);
  const compile = page.getByRole("button", { name: "Compile", exact: true });
  const confirm = page.getByRole("alertdialog", { name: "Start the draft afresh?" });
  await compile.click();
  await expect(confirm).toContainText("loses the edits on its Criterion cards");
  await confirm.getByRole("button", { name: "Keep the draft" }).click();
  expect((await grasps())?.threshold).toBe(0); // kept

  await compile.click();
  await confirm.getByRole("button", { name: "Start afresh" }).click();

  await expect(confirm).toBeHidden();
  await expect.poll(async () => (await grasps())?.threshold).not.toBe(0); // compiled afresh
  // Compiled, the composer is a chat with Spark again.
  await expect(page.getByRole("textbox", { name: "Message Spark" })).toBeVisible();
  expect(errors).toEqual([]);
});
