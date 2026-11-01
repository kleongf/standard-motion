import { expect, test, type APIRequestContext } from "@playwright/test";

import {
  askVisual,
  boxForPlacement,
  EPISODES,
  episodeId,
  ingest,
  referenceLabel,
} from "./helpers.ts";

// Two Episodes Winnow keeps on its own: each grasps cleanly and, boxed in Exterior 2 with the
// target drawn, has a healthy track ending on it. The sample holds every revealed auto-Keep
// outside the Test set, so it holds both; this asserts on them only.
const [FIRST, SECOND] = [episodeId(EPISODES.audit[0]), episodeId(EPISODES.audit[1])];
const NEVER_DROPS = "never drops it";

async function triage(request: APIRequestContext, id: string) {
  const response = await request.get(`/api/episodes/${encodeURIComponent(id)}/triage`);
  return (await response.json()) as {
    decision: string;
    criteria: { criterion_id: string; uncertainty: string | null }[];
  };
}

async function decision(request: APIRequestContext, id: string): Promise<string> {
  return (await triage(request, id)).decision;
}

/** Whether Spark has answered the Episode's placement question; unasked, it's "source missing". */
async function placementAnswered(request: APIRequestContext, id: string): Promise<boolean> {
  const placed = (await triage(request, id)).criteria.find(
    (c) => c.criterion_id === "placed-on-target",
  );
  return placed !== undefined && placed.uncertainty !== "source missing";
}

test.beforeEach(async ({ request }) => {
  await ingest(request, EPISODES.audit);
  await referenceLabel(request, [FIRST, SECOND]);
  // Spark's placement answers are scripted for the unboxed clips, so ask before boxing (as the
  // triage spec does); asking again once boxed would cut a clip with no recorded answer.
  const unasked = [];
  for (const index of EPISODES.audit) {
    if (!(await placementAnswered(request, episodeId(index)))) unasked.push(index);
  }
  if (unasked.length > 0) await askVisual(request, unasked);
  for (const id of [FIRST, SECOND]) await boxForPlacement(request, id);
  for (const id of [FIRST, SECOND]) expect(await decision(request, id)).toBe("keep");
});

test("auditing one Keep Good and another Bad updates Keep precision", async ({ page, request }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await page.goto("/?page=audit");

  const draw = page.getByRole("button", { name: "Draw the sample" });
  const precision = page.getByTestId("audit-precision");
  await expect(draw.or(precision)).toBeVisible();
  if (await draw.isVisible()) await draw.click();
  await expect(
    page.getByText(/marked · Rubric v\d+ · seed \d+ · drawn at s = 1\.0$/),
  ).toBeVisible();
  await expect(precision).toHaveText("No Keeps marked yet");

  const strip = page.getByRole("region", { name: "Sample" });
  const item = (id: string) => strip.getByRole("button").filter({ hasText: id });
  await expect(item(FIRST)).toContainText("Keep · Not marked");
  await expect(item(SECOND)).toContainText("Keep · Not marked");

  await item(FIRST).click();
  await expect(page.getByTestId("audit-current")).toHaveText(FIRST);
  const call = page.getByRole("region", { name: "Your audit" });
  await call.getByRole("button", { name: "Good" }).click();
  await expect(item(FIRST)).toContainText("Keep · Good");
  await expect(precision).toHaveText("1/1 good · 95% CI 0.21–1.00 · ≥ 0.10 (90%)");

  await item(SECOND).click();
  await expect(page.getByTestId("audit-current")).toHaveText(SECOND);
  await call.getByRole("button", { name: "Bad…" }).click();
  await call.getByRole("button", { name: `“${NEVER_DROPS}”` }).click();
  await expect(call.getByTestId("audit-mark")).toHaveText(`Marked Bad: “${NEVER_DROPS}”`);
  await expect(item(SECOND)).toContainText("Keep · Bad");
  await expect(precision).toHaveText(/^1\/2 good · 95% CI 0\.\d\d–0\.\d\d$/);

  // An audit label measures precision only: Winnow's Triage decision stands.
  expect(await decision(request, SECOND)).toBe("keep");
  expect(errors).toEqual([]);
});
