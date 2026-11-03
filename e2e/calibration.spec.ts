import { expect, test, type Page, type Route } from "@playwright/test";

import type { components } from "../frontend/src/api/schema.ts";
import { freezeDevSet } from "./helpers.ts";

type Calibration = components["schemas"]["Calibration"];
type RubricVersion = components["schemas"]["RubricVersion"];
type AnchorPreview = components["schemas"]["AnchorPreview"];
type AcceptedSuggestion = components["schemas"]["AcceptedSuggestion"];

// The Rubric version in use shows its margin multiplier s, calibrates it, and offers the
// thresholds labels suggest. The e2e Dev set is one Episode, so no Criterion can have the two
// contradicting labels a suggestion needs, and calibrating the version every spec scores with
// would change their margins: the uncalibrated state is the server's, and the scan's and
// accept's replies are stubbed here (backend/tests/calibration covers them for real).
const GRASP = "Grasp attempts, up to and including the grasp, ≤ 1";
const SUGGESTED = "Grasp attempts, up to and including the grasp, ≤ 1.5";

function calibrated(version: number): Calibration {
  return {
    rubric_version: version,
    s: 2,
    record: {
      rubric_version: version,
      s: 2,
      n_labels: 12,
      errors: 1,
      bound_met: true,
      unstable: true,
      created_at: "2026-10-30T00:00:00+00:00",
    },
    labelled: 12,
    grid: [2, 1.5, 1, 0.75, 0.5],
    max_error_rate: 0.2,
    confidence: 0.9,
    suggestions: [
      {
        criterion_id: "grasp-attempts",
        phrase: "grasps the object on the first try",
        english: GRASP,
        suggested_english: SUGGESTED,
        threshold: 1,
        unit: "attempts",
        suggested_threshold: 1.5,
        suggested_margin: 1,
        contradicting: 2,
        labelled: 3,
      },
    ],
  };
}

function uncalibrated(version: number): Calibration {
  return { ...calibrated(version), s: 1, record: null, suggestions: [] };
}

/** `inUse` with the grasp threshold at 1.5, frozen as the next version. */
function acceptedVersion(inUse: RubricVersion): RubricVersion {
  const criteria = inUse.rubric.criteria.map((c) =>
    c.id === "grasp-attempts" ? { ...c, threshold: 1.5, margin: 1, assumptions: [] } : c,
  );
  return {
    ...inUse,
    version: inUse.version + 1,
    origin: "run",
    created_at: "2026-10-30T00:00:00+00:00",
    rubric: { ...inUse.rubric, criteria },
  };
}

/** Serve `next` as the version in use: in the list, as the Rubric, and with v`from`'s
 * anchor-pool preview read at its threshold. */
async function serveVersion(page: Page, next: RubricVersion, from: number): Promise<void> {
  await page.route("**/api/rubric", async (route: Route) => {
    await route.fulfill({ json: next });
  });
  await page.route("**/api/rubric/versions", async (route: Route) => {
    const versions = (await (await route.fetch()).json()) as RubricVersion[];
    await route.fulfill({ json: [next, ...versions] });
  });
  await page.route(`**/api/rubric/versions/${String(next.version)}/preview`, async (route) => {
    const url = route
      .request()
      .url()
      .replace(`/${String(next.version)}/`, `/${String(from)}/`);
    const preview = (await (await route.fetch({ url })).json()) as AnchorPreview;
    const criteria = preview.criteria.map((c) =>
      c.criterion_id === "grasp-attempts" ? { ...c, english: SUGGESTED, threshold: 1.5 } : c,
    );
    await route.fulfill({
      json: { ...preview, rubric_version: next.version, criteria } satisfies AnchorPreview,
    });
  });
}

test("the version in use calibrates s and accepts a suggested threshold", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await freezeDevSet(request);
  const inUse = (await (await request.get("/api/rubric")).json()) as RubricVersion;
  const v = inUse.version;

  await page.goto(`/?page=describe&version=${String(v)}`);
  const control = page.getByRole("region", { name: "Calibration" });
  await expect(control.getByTestId("multiplier")).toHaveText("s = 1.0 · not tuned yet");

  // From here the replies are stubbed: twelve labels to tune on, then the scan's result, then
  // the next version, which keeps the s its suggestion was made at.
  let shown: Calibration = { ...uncalibrated(v), labelled: 12 };
  await page.route("**/api/calibration", async (route: Route) => {
    await route.fulfill({ json: shown });
  });
  await page.route("**/api/calibration/run", async (route: Route) => {
    shown = calibrated(v);
    await route.fulfill({ json: shown });
  });
  await page.reload();
  await control.getByRole("button", { name: "Calibrate" }).click();
  await expect(control.getByTestId("multiplier")).toHaveText("s = 2.0 · tuned on 12 labels");
  await expect(control.getByTestId("calibration-warning")).toHaveText(
    "Margins unstable: label more. Dropping 2 labels moves s.",
  );

  // The suggestion sits on its card, with its line on the histogram.
  const card = page.getByRole("article", { name: GRASP });
  const suggestion = card.getByTestId("threshold-suggestion");
  await expect(suggestion).toContainText("Labels suggest");
  await expect(suggestion).toContainText("≤ 1.5");
  await expect(card.getByTestId("suggested-line")).toBeAttached();

  // Accepting freezes the next version, which shows the suggested threshold at the same s.
  const next = acceptedVersion(inUse);
  let accepted = "";
  await page.route("**/api/calibration/suggestions/*/accept", async (route: Route) => {
    accepted = new URL(route.request().url()).pathname;
    shown = { ...calibrated(next.version), suggestions: [] };
    await serveVersion(page, next, v);
    const reply: AcceptedSuggestion = {
      version: next,
      draft_updated: true,
      draft_note: "The draft's Criterion grasp-attempts moved too.",
    };
    await route.fulfill({ status: 201, json: reply });
  });
  await suggestion.getByRole("button", { name: `Accept as v${String(next.version)}` }).click();

  await expect(page).toHaveURL(new RegExp(`version=${String(next.version)}`));
  expect(accepted).toBe("/api/calibration/suggestions/grasp-attempts/accept");
  await expect(page.getByTestId("accept-note")).toHaveText(
    `v${String(next.version)} froze the suggested threshold. The draft's Criterion grasp-attempts moved too.`,
  );
  await expect(page.getByRole("article", { name: SUGGESTED })).toBeVisible();
  await expect(control.getByTestId("multiplier")).toHaveText("s = 2.0 · tuned on 12 labels");
  await expect(page.getByText(/^Run \d/)).toBeVisible();
  expect(errors).toEqual([]);
});

test("Describe's default view calibrates the version in use and points to its suggestions", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  const v = ((await (await request.get("/api/rubric")).json()) as RubricVersion).version;

  await page.goto("/?page=describe");
  const control = page.getByRole("region", { name: "Calibration" });
  await expect(page.getByText(`Rubric v${String(v)} is in use.`)).toBeVisible();
  await expect(control.getByTestId("multiplier")).toHaveText("s = 1.0 · not tuned yet");

  // Stubbed from here, as above: labels to tune on, then the scan's result with a suggestion.
  let shown: Calibration = { ...uncalibrated(v), labelled: 12 };
  await page.route("**/api/calibration", async (route: Route) => {
    await route.fulfill({ json: shown });
  });
  await page.route("**/api/calibration/run", async (route: Route) => {
    shown = calibrated(v);
    await route.fulfill({ json: shown });
  });
  await page.reload();
  await control.getByRole("button", { name: "Calibrate" }).click();
  await expect(control.getByTestId("multiplier")).toHaveText("s = 2.0 · tuned on 12 labels");

  await page
    .getByRole("button", { name: `See the threshold your labels suggest on v${String(v)}` })
    .click();
  await expect(page).toHaveURL(new RegExp(`version=${String(v)}`));
  await expect(page.getByTestId("threshold-suggestion")).toContainText("≤ 1.5");
  expect(errors).toEqual([]);
});
