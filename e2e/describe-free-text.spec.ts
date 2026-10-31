import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { FROZEN, freezeDevSet, undoInterview } from "./helpers.ts";

// Spark's readings of these words are scripted (backend/tests/record_interview.py), each on STEADY
// freshly compiled, whose first question is about the Unsupported Phrase "never drops it". Like
// the other interview specs it claims no Episode, and afterEach compiles the frozen Description
// again for the other describe specs.
const NEVER_DROPS = "never drops it";
const STEADY = `Steady pick: grasps it once, ${NEVER_DROPS}.`;
const PICK_TEXT = "That's just how a steady pick looks, there's nothing to check.";
const CHANGE_TEXT = "It means it grasps once and holds on: it never needs a second grasp.";
const EDIT_TEXT = "It should also finish within 20 seconds.";

async function compile(request: APIRequestContext, description: string): Promise<void> {
  const compiled = await request.post("/api/rubric/draft/compile", {
    data: { description, fresh: true },
  });
  expect(compiled.ok()).toBe(true);
}

async function say(page: Page, words: string): Promise<void> {
  await page.getByRole("textbox", { name: "Message Spark" }).fill(words);
  await page.getByRole("button", { name: "Send" }).click();
}

test.beforeEach(async ({ request }) => {
  await freezeDevSet(request);
  await compile(request, STEADY);
});

test.afterEach(async ({ request }) => {
  await undoInterview(request);
  await compile(request, FROZEN);
});

test("words to the question being asked pick the answer they mean", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await page.goto("/?page=describe");
  const interview = page.getByRole("region", { name: "Interview" });
  await expect(interview.getByRole("region", { name: "Question" })).toContainText(NEVER_DROPS);
  await expect(page.getByTestId("replying-to")).toContainText("Replying to Unsupported Phrase");

  await say(page, PICK_TEXT);

  await expect(interview.getByText(PICK_TEXT)).toBeVisible(); // the curator's bubble
  await expect(interview.getByTestId("spark-reply")).not.toBeEmpty();
  await expect(interview.getByRole("article", { name: `Answer: ${NEVER_DROPS}` })).toContainText(
    `“${NEVER_DROPS}”: marked Context`,
  );
  await expect(page.getByRole("textbox", { name: "Message Spark" })).toHaveValue("");
  expect(errors).toEqual([]);
});

test("words that say what a Phrase means recompile only that Phrase", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await page.goto("/?page=describe");
  const drops = page.getByRole("region", { name: `Phrase: ${NEVER_DROPS}` });
  await expect(drops.getByTestId("phrase-status")).toHaveText("Unsupported");

  await say(page, CHANGE_TEXT);

  await expect(page.getByTestId("spark-reply")).not.toBeEmpty();
  await expect(drops.getByTestId("phrase-status")).toHaveText("Checked");
  expect(errors).toEqual([]);
});

test("with the question set aside, words edit the Description", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await page.goto("/?page=describe");
  await page.getByRole("button", { name: "Talk about the Description instead" }).click();
  await expect(page.getByTestId("replying-to")).toHaveCount(0);

  await say(page, EDIT_TEXT);

  await expect(page.getByTestId("spark-reply")).not.toBeEmpty();
  await expect(page.getByTestId("compiled-description")).toHaveText(
    `${STEADY.slice(0, -1)}, within 20 s.`,
  );
  expect(errors).toEqual([]);
});
