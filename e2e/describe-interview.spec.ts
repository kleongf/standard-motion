import { expect, test } from "@playwright/test";

import { clickCompile, freezeDevSet, openDescription } from "./helpers.ts";

// The frozen Description, whose compile against the Dev set is recorded: every Phrase is covered,
// and Spark assumed its thresholds, the pause one among them.
const FROZEN =
  "Expert pick-and-place: grasps the object on the first try, never drops it, places it in or " +
  "on the target named in the instruction, no long pauses.";
const PAUSES = "Longest stretch with the arm under 0.01 m/s < 1 s";

test("with every Phrase covered, a bisection card confirms the pause threshold", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await freezeDevSet(request); // one Dev set Episode, which never pauses

  await page.goto("/?page=describe");
  await openDescription(page);
  await page.getByLabel("Description", { exact: true }).fill(FROZEN);
  // Other specs (and earlier runs) leave drafts behind: read the interview only once it is the
  // one for this compile, fetched after the compile returned.
  let compiled = false;
  const compiling = page.waitForResponse((r) => {
    if (r.url().endsWith("/api/rubric/draft/compile") && r.ok()) compiled = true;
    return compiled;
  });
  const fresh = page.waitForResponse(
    (r) => compiled && r.url().endsWith("/api/interview") && r.request().method() === "GET",
  );
  await clickCompile(page, request, FROZEN);
  await compiling;
  await fresh;

  const interview = page.getByRole("region", { name: "Interview" });
  const question = interview.getByRole("region", { name: "Question" });
  await expect(interview.getByTestId("interview-status")).toHaveText(
    /^Every Phrase is covered: the interview is done\./,
  );

  // Assumed thresholds are asked on the anchor Episode; skip the others to reach the pauses.
  await expect(question).toContainText(/Is .+ fine for “/);
  for (let i = 0; i < 4; i++) {
    const asked = (await question.textContent()) ?? "";
    if (asked.includes("no long pauses")) break;
    await question.getByRole("button", { name: /^Skip/ }).click();
    await expect(question).not.toHaveText(asked); // the next question is up
  }
  const pauses = page.getByRole("article", { name: PAUSES });
  await expect(pauses.getByTestId("assumption")).toHaveCount(1);
  await expect(question).toContainText(/Is .+ s fine for “no long pauses”\?/);
  await expect(question.getByLabel("Episode clip")).toBeVisible();
  await question.getByRole("button", { name: "Fine: “no long pauses” passes" }).click();

  const answered = interview.getByRole("article", { name: "Answer: no long pauses" });
  await expect(answered.getByTestId("answer-effect")).toHaveText(
    /^Labelled droid_100:6 pass on “no long pauses”\. Threshold confirmed at 1 s\.$/,
  );
  await expect(pauses).toHaveAttribute("data-highlighted", "true");
  await expect(pauses.getByTestId("assumption")).toHaveCount(0);

  // Undo puts the assumption back and asks again.
  await answered.getByRole("button", { name: "Undo" }).click();
  await expect(pauses.getByTestId("assumption")).toHaveCount(1);
  await expect(pauses).not.toHaveAttribute("data-highlighted");
  await expect(question).toContainText("fine for “no long pauses”?");
  expect(errors).toEqual([]);
});
