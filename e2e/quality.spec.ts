import { expect, test, type Page, type Route } from "@playwright/test";

import type { components } from "../frontend/src/api/schema.ts";
import { EPISODES, episodeId, ingest, referenceLabel } from "./helpers.ts";

type TriageList = components["schemas"]["TriageList"];

// Quality comes from soft Criteria, and the Rubric every spec scores with has none. Running one
// with a soft Criterion would change that Rubric for every later spec, and no Run could put it
// back: the frozen Description compiles to a different Rubric than the seeded one. So the
// table's reply is stubbed with qualities in the order these two Episodes would get with the
// release height soft (BETTER releases 5.3 cm above where it picked up, WORSE 6.5 cm); their
// values depend on the whole run. backend/tests/triage/test_quality_api.py scores them for real.
const [BETTER, WORSE] = EPISODES.quality;
const OWN: readonly number[] = EPISODES.quality;
const QUALITY = new Map([
  [episodeId(BETTER), 0.67],
  [episodeId(WORSE), -1.35],
]);

const row = (page: Page, index: number) =>
  page.getByRole("row", { name: new RegExp(`^${String(index)} `) });

/** The table's Episode indices in order, this spec's only: other specs' Episodes show too. */
const ownRows = (page: Page) => async () =>
  (await page.locator("tbody tr td:first-child").allTextContents())
    .map(Number)
    .filter((index) => OWN.includes(index));

/** Serve the triage list with this spec's Episodes' qualities. */
async function serveQualities(page: Page): Promise<void> {
  await page.route("**/api/triage", async (route: Route) => {
    const list = (await (await route.fetch()).json()) as TriageList;
    const rows = list.rows.map((r) => ({ ...r, quality: QUALITY.get(r.episode_id) ?? r.quality }));
    await route.fulfill({ json: { ...list, rows } satisfies TriageList });
  });
}

test.beforeEach(async ({ request }) => {
  await ingest(request, OWN);
  await referenceLabel(request, OWN.map(episodeId));
});

test("the table sorts by quality, and the Workstation shows it", async ({ page, request }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  // Unstubbed, with no soft Criterion in use, nothing has a quality.
  const real = (await (await request.get("/api/triage")).json()) as TriageList;
  expect(real.rows.filter((r) => QUALITY.has(r.episode_id)).map((r) => r.quality)).toEqual([
    null,
    null,
  ]);
  await serveQualities(page);
  await page.goto("/?page=episodes");
  await expect(row(page, BETTER).getByTestId("quality")).toHaveText("+0.67");
  await expect(row(page, WORSE).getByTestId("quality")).toHaveText("−1.35");

  const quality = page.getByRole("button", { name: "Quality" });
  await quality.click();
  await expect.poll(ownRows(page)).toEqual([BETTER, WORSE]); // best first
  await expect(page).toHaveURL(/sort=-quality/);
  await quality.click();
  await expect.poll(ownRows(page)).toEqual([WORSE, BETTER]); // worst first
  await quality.click();
  await expect(page).not.toHaveURL(/sort=/);

  await row(page, BETTER).click();
  await expect(page.getByTestId("quality")).toHaveText(
    "Quality +0.67 · from soft Criteria, relative to the run",
  );
  expect(errors).toEqual([]);
});
