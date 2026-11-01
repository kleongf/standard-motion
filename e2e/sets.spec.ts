import { expect, test } from "@playwright/test";

import { askVisual, EPISODES, episodeId, freezeDevSet, referenceLabel } from "./helpers.ts";

const [INDEX] = EPISODES.sets;
const EPISODE = episodeId(INDEX);

test("Prepare shows each set's size and frozen state; Episodes show their set", async ({
  page,
  request,
}) => {
  // Sets are defined with the CLI or the API; freezing is permanent for this server's data dir.
  // Only freezeDevSet touches the Dev set.
  await freezeDevSet(request);
  await referenceLabel(request, [EPISODE]); // so its Triage decision shows
  await askVisual(request, [INDEX]); // Spark sees its object placed on its target

  await page.goto("/?page=prepare");

  await expect(page.getByTestId("set-dev")).toContainText(/Dev set\s*1 Episode\s*frozen /);
  await expect(page.getByTestId("set-test")).toContainText("not frozen");

  await page.goto("/?page=episodes");
  const row = `^${String(INDEX)} `;
  // Never boxed (compile's recording expects the Dev set unboxed), so placement needs review.
  await expect(
    page.getByRole("row", { name: new RegExp(`${row}.* Dev set Needs review`) }),
  ).toBeVisible();
  await page.getByRole("row", { name: new RegExp(row) }).click();
  await expect(page.getByTestId("episode-set")).toHaveText("Dev set");
});
