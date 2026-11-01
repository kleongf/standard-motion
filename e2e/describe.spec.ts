import { expect, test } from "@playwright/test";

import { clickCompile, freezeDevSet, openDescription } from "./helpers.ts";

// The frozen Description, whose compile against the Dev set is recorded.
const FROZEN =
  "Expert pick-and-place: grasps the object on the first try, never drops it, places it in or " +
  "on the target named in the instruction, no long pauses.";

test("a Description compiles into a Rubric draft: Phrases tinted and linked to Criteria", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await freezeDevSet(request);

  await page.goto("/?page=describe");
  await expect(page.getByTestId("anchor-pool")).toHaveText(
    /^Anchor pool: Dev set · 1 Episode · \d+ Test set Episodes? hidden$/,
  );
  await openDescription(page);
  await page.getByLabel("Description", { exact: true }).fill(FROZEN);
  await clickCompile(page, request, FROZEN);

  const description = page.getByTestId("compiled-description");
  const phrase = (text: string) => description.getByRole("link", { name: text, exact: true });
  await expect(phrase("grasps the object on the first try")).toHaveAttribute(
    "data-status",
    "checked",
  );
  await expect(phrase("Expert pick-and-place:")).toHaveAttribute("data-status", "context");
  await expect(phrase("never drops it")).toHaveAttribute("data-status", "checked");
  await expect(description.getByTestId("uncovered-word")).toHaveCount(0);

  // A Phrase links to its section: status, reason, and its Criteria in English.
  await phrase("no long pauses").click();
  const pauses = page.getByRole("region", { name: "Phrase: no long pauses" });
  await expect(pauses).toBeInViewport();
  await expect(pauses.getByTestId("phrase-status")).toHaveText("Checked");
  await expect(
    pauses.getByRole("article", { name: "Longest stretch with the arm under 0.01 m/s < 1 s" }),
  ).toBeVisible();
  await expect(pauses.getByTestId("assumption")).toContainText("Assumed: ");
  const drops = page.getByRole("region", { name: "Phrase: never drops it" });
  await expect(
    drops.getByRole("article", {
      name: "Time the object is out of the closed gripper (wrist view), while holding, ≤ 0.2 s",
    }),
  ).toBeVisible();
  const framing = page.getByRole("region", { name: "Phrase: Expert pick-and-place:" });
  await expect(framing.getByTestId("phrase-reason")).not.toBeEmpty(); // Context says why

  // The Rubric-level settings start assumed.
  await expect(page.getByTestId("rubric-setting")).toHaveCount(2);
  await expect(page.getByTestId("rubric-setting").first()).toContainText("assumed");

  // The draft is kept.
  await page.reload();
  await expect(phrase("grasps the object on the first try")).toBeVisible();
  expect(errors).toEqual([]);
});
