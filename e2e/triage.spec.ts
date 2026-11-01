import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import {
  askVisual,
  boxForPlacement,
  EPISODES,
  episodeId,
  ingest,
  referenceLabel,
} from "./helpers.ts";

// Two Episodes that release inside the release height's margin (LESS_SURE nearer its fail
// side), one that fails its grasp twice first, and one kept. All four are boxed in Exterior 2:
// REJECT's recorded track there is empty, so its placement is unsure with "track lost".
const [NEAR, REJECT, KEEP, LESS_SURE] = EPISODES.triage;
const OWN: readonly number[] = EPISODES.triage;

const row = (page: Page, index: number) =>
  page.getByRole("row", { name: new RegExp(`^${String(index)} `) });

/** The table's Episode indices in order, this spec's only: other specs' Episodes show too. */
const ownRows = (page: Page) => async () =>
  (await page.locator("tbody tr td:first-child").allTextContents())
    .map(Number)
    .filter((index) => OWN.includes(index));

/** Whether Spark has answered the Episode's placement question; unasked, it's "source missing". */
async function placementAnswered(request: APIRequestContext, index: number): Promise<boolean> {
  const response = await request.get(
    `/api/episodes/${encodeURIComponent(episodeId(index))}/triage`,
  );
  const triage = (await response.json()) as {
    criteria: { criterion_id: string; uncertainty: string | null }[];
  };
  const placed = triage.criteria.find((c) => c.criterion_id === "placed-on-target");
  return placed !== undefined && placed.uncertainty !== "source missing";
}

test.beforeEach(async ({ request }) => {
  await ingest(request, EPISODES.triage);
  // Their Triage decisions show only once labelled.
  await referenceLabel(request, EPISODES.triage.map(episodeId));
  // Spark sees each object placed on its target. Asked once, before boxing, on the whole view its
  // scripted answers were recorded for; answers don't depend on the box, so they still apply.
  // Asking again once boxed would cut a placement clip with no recorded answer.
  const unasked = [];
  for (const index of EPISODES.triage) {
    if (!(await placementAnswered(request, index))) unasked.push(index);
  }
  if (unasked.length > 0) await askVisual(request, unasked);
  for (const index of EPISODES.triage) await boxForPlacement(request, episodeId(index));
});

test("the table sorts Episodes into Triage tabs with their Reasons", async ({ page }) => {
  await page.goto("/?page=episodes");

  await expect(page.getByText(/\d+ of \d+ decided automatically/)).toBeVisible();
  await page.getByRole("tab", { name: /^Keep/ }).click();
  await expect(
    page.getByRole("row", { name: new RegExp(`^${String(KEEP)} Put the marker in the pot`) }),
  ).toBeVisible();
  await expect(row(page, REJECT)).toHaveCount(0);

  await page.getByRole("tab", { name: /^Reject/ }).click();
  await expect(row(page, REJECT)).toContainText(
    "2 failed grasp attempts, at 0.9 s and 1.3 s, before the grasp at 1.8 s.",
  );
  await expect(page).toHaveURL(/triage=reject/);
});

test("a Reject opens from the table, and its lane and Reason seek the playhead", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await page.goto("/?page=episodes&triage=reject");

  await row(page, REJECT).click();

  await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toContainText(
    episodeId(REJECT),
  );
  await expect(page.getByTestId("triage-decision")).toHaveText("Reject");
  await expect(page.getByText("0.0 / 3.0 s")).toBeVisible();
  await page.getByRole("button", { name: /^Lane: Grasp attempts/ }).click();
  // The first failed attempt, at 0.9 s; its result opens with its moments.
  await expect(page.getByText("0.9 / 3.0 s")).toBeVisible();
  await expect(page.getByRole("button", { name: "Grasp 1.8 s" })).toBeVisible();

  // The Reason shows one line; More opens the rest when it overflows.
  const more = page.getByRole("button", { name: "More", exact: true });
  if (await more.isVisible()) await more.click();
  await page.getByTestId("reason").getByRole("button", { name: "1.3 s" }).click();
  await expect(page.getByText("1.3 / 3.0 s")).toBeVisible();
  expect(errors).toEqual([]);
});

test("the table filters by Uncertainty signal, set and Phrase, and sorts by confidence", async ({
  page,
}) => {
  const own = ownRows(page);
  await page.goto("/?page=episodes");

  await page.getByLabel("Uncertainty signal").selectOption("near threshold");
  await expect.poll(own).toEqual([NEAR, LESS_SURE]);
  await expect(row(page, NEAR).getByTestId("phrase-chip")).toHaveText("never drops it");
  await expect(page).toHaveURL(/signal=near\+threshold/);

  await page.getByRole("button", { name: "Confidence" }).click();
  await expect.poll(own).toEqual([LESS_SURE, NEAR]); // least confident first
  const confidence = async (index: number) =>
    Number(await row(page, index).getByTestId("confidence").textContent());
  expect(await confidence(LESS_SURE)).toBeLessThan(await confidence(NEAR));
  await page.getByRole("button", { name: "Confidence" }).click();
  await expect.poll(own).toEqual([NEAR, LESS_SURE]);

  await page.getByLabel("Set", { exact: true }).selectOption("dev");
  await expect.poll(own).toEqual([]);
  await page.getByLabel("Set", { exact: true }).selectOption("none");
  await expect.poll(own).toEqual([NEAR, LESS_SURE]);

  await page.getByLabel("Uncertainty signal").selectOption("track lost");
  await expect.poll(own).toEqual([REJECT]);

  await page.getByRole("button", { name: "Clear filters" }).click();
  await page.getByLabel("Phrase").selectOption("grasps the object on the first try");
  await expect(row(page, REJECT)).toBeVisible();
  await expect(row(page, KEEP)).toHaveCount(0);
});

test("the Workstation plots each tracked Criterion's deciding signal", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await page.goto(`/?page=episodes&episode=${encodeURIComponent(episodeId(KEEP))}`);

  await expect(page.getByTestId("triage-decision")).toHaveText("Keep");
  for (const id of ["in-hand-lost", "fall-after-release", "final-overlap"])
    await expect(page.getByTestId(`track-plot-${id}`)).toBeVisible();
  const overlap = page.getByTestId("track-plot-final-overlap");
  await expect(overlap).toContainText("Share inside the target box");

  // Clicking a plot opens its result on the view it was tracked in, at that time.
  await overlap.getByRole("img").click();
  await expect(page.getByLabel("Episode video")).toHaveAttribute("src", /exterior_image_2_left$/);
  await expect(page.getByTestId("criterion-final-overlap")).toContainText(
    "of the object's final box is inside the target box",
  );
  expect(errors).toEqual([]);
});
