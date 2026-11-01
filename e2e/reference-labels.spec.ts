import { expect, test } from "@playwright/test";

import { EPISODES, episodeId, ingest } from "./helpers.ts";

// It has no instruction and a failing Dataset outcome. sets.spec.ts freezes the Dev set, so this
// one labels from the Test set, which nothing freezes.
const EPISODE = episodeId(EPISODES.referenceLabels[0]);

interface Label {
  episode_id: string;
  relabel: boolean;
  instruction: string | null;
  elapsed_s: number;
  phrases: {
    phrase: string;
    passed: boolean;
    interval: { start_s: number; end_s: number } | null;
  }[];
}

test("labelling a Test set Episode blind stores its Phrases, interval and instruction", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await ingest(request, EPISODES.referenceLabels);
  await request.post("/api/sets/test/episodes", { data: { episode_ids: [EPISODE] } });

  await page.goto("/?page=reference");
  await expect(page.getByTestId(`outcome-${EPISODE}`)).toHaveText("");
  await page.getByRole("row", { name: new RegExp(`^${EPISODE} `) }).click();

  // The Workstation, with every output hidden: no tracks, no box overlay, no results panel.
  await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toContainText(EPISODE);
  await page.getByRole("tab", { name: "Wrist" }).click();
  await expect(page.getByLabel("Episode video")).toHaveAttribute("src", /wrist_image_left$/);
  await expect(page.getByTestId("track-box")).toHaveCount(0);
  await expect(page.getByTestId("track-status-wrist")).toHaveCount(0);
  await expect(page.getByText("Triage decision")).toHaveCount(0);
  await expect(page.getByTestId("triage-decision")).toHaveCount(0);
  await expect(page.getByTestId("reason")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Lane: / })).toHaveCount(0);
  await expect(page.getByTestId("label-timer")).toHaveText(/^0:0[1-9]$/);

  const save = page.getByRole("button", { name: "Save & next" });
  for (const phrase of ["grasps the object", "places it in or on", "no long pauses"]) {
    await page
      .getByRole("group", { name: new RegExp(`^${phrase}`) })
      .getByRole("button", { name: "Pass" })
      .click();
  }
  const drops = page.getByRole("group", { name: "never drops it" });
  await drops.getByRole("button", { name: "Pass" }).click();
  await drops.getByRole("button", { name: "Fail" }).click(); // a change of mind
  await expect(drops.getByRole("button", { name: "Fail" })).toHaveAttribute("aria-pressed", "true");
  await expect(drops.getByRole("button", { name: "Pass" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  await expect(page.getByText("Mark where “never drops it” fails")).toBeVisible();
  await expect(save).toBeDisabled();

  await page.getByLabel("Playhead").fill("0.6");
  await drops.getByRole("button", { name: "Mark start" }).click();
  await page.getByLabel("Playhead").fill("1.2");
  await drops.getByRole("button", { name: "Mark end" }).click();
  await expect(drops.getByRole("button", { name: "End 1.2 s" })).toBeVisible();
  await expect(save).toBeDisabled(); // the Episode has no instruction yet
  await page.getByLabel(/^Instruction/).fill("Put the red block on the plate");
  await save.click();

  // Back at the queue, now empty; the Dataset outcome shows only now.
  await expect(page.getByRole("button", { name: "Start labelling (0)" })).toBeVisible();
  await expect(page.getByTestId(`outcome-${EPISODE}`)).toHaveText("failure");

  const labels = (await (await request.get("/api/reference-labels")).json()) as Label[];
  const saved = labels.find((l) => l.episode_id === EPISODE && !l.relabel);
  expect(saved?.instruction).toBe("Put the red block on the plate");
  expect(saved?.elapsed_s).toBeGreaterThan(0);
  expect(saved?.phrases.map((p) => [p.passed, p.interval])).toEqual([
    [true, null],
    [false, { start_s: 0.6, end_s: 1.2 }],
    [true, null],
    [true, null],
  ]);
  expect(errors).toEqual([]);
});
