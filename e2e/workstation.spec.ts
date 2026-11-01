import { expect, test } from "@playwright/test";

import { askVisual, EPISODES, episodeId, ingest, referenceLabel } from "./helpers.ts";

// Adjacent in the table, so J and K step between them: FIRST grasps cleanly, SECOND is a
// "Move the black remote control" Episode (index % 3 == 1) whose scripted visual samples split.
const [FIRST, SECOND] = EPISODES.workstation;
const open = (index: number, t?: number) =>
  `/?page=episodes&episode=${encodeURIComponent(episodeId(index))}` +
  (t === undefined ? "" : `&t=${String(t)}`);

test.beforeEach(async ({ request }) => {
  await ingest(request, EPISODES.workstation);
});

test("a row opens the Workstation; camera tabs switch the video", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await page.goto("/?page=episodes");

  const row = new RegExp(`^${String(SECOND)} Move the black remote control`);
  await page.getByRole("row", { name: row }).click();

  await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toContainText(
    episodeId(SECOND),
  );
  const video = page.getByLabel("Episode video");
  await expect(video).toHaveAttribute("src", /exterior_image_1_left$/);
  await page.getByRole("tab", { name: "Wrist" }).click();
  await expect(video).toHaveAttribute("src", /wrist_image_left$/);
  await expect(page.getByRole("img", { name: "Gripper over the Episode" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("the playhead moves the plots' readouts, and ?t= opens at that time", async ({ page }) => {
  await page.goto(open(FIRST, 2));

  // The fixture gripper is closed from 0.9 s to 2.4 s, open before and after.
  await expect(page.getByText("2.0 / 3.0 s")).toBeVisible();
  await expect(page.getByTestId("readout-gripper")).toHaveText("1.00");
  await page.getByLabel("Playhead").fill("0.2");
  await expect(page.getByTestId("readout-gripper")).toHaveText("0.00");
});

test("the wrist view shows SAM's box following the playhead", async ({ page }) => {
  await page.goto(open(FIRST, 0.2));
  await page.getByRole("tab", { name: "Wrist" }).click();

  // The fixture's block slides right; its recorded wrist track follows it.
  const box = page.getByTestId("track-box");
  const left = () => box.evaluate((el) => parseFloat((el as HTMLElement).style.left));
  await expect(box).toBeVisible();
  const before = await left();
  await page.getByLabel("Playhead").fill("2.4");
  await expect.poll(left).toBeGreaterThan(before + 10);
  await expect(page.getByTestId("track-status-wrist")).toHaveText("box on 15 of 15 frames");
});

test("a visual Criterion shows each of Spark's samples and the clip it watched", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await referenceLabel(request, [episodeId(SECOND)]); // its outputs show once labelled
  await askVisual(request, [SECOND]); // scripted to split 2-1

  await page.goto(open(SECOND));
  const result = page.getByTestId("criterion-placed-on-target");
  await result.getByRole("button", { name: /Is the object resting in or on the target/ }).click();
  await expect(result).toContainText("samples split"); // why it is unsure, once opened

  const evidence = result.getByTestId("visual-evidence");
  const samples = evidence.getByRole("list", { name: "Spark's samples" }).getByRole("listitem");
  await expect(samples).toHaveCount(3);
  await expect(samples.filter({ hasText: "fail · confidence" })).toHaveCount(1);
  await expect(evidence.getByLabel("Clip Spark watched")).toHaveAttribute(
    "src",
    new RegExp(`/api/episodes/droid_100%3A${String(SECOND)}/visual-clips/[0-9a-f]{16}\\.mp4$`),
  );
  await expect(evidence).toContainText("exterior_image_1_left");
  expect(errors).toEqual([]);
});

test("J and K step through Episodes and Esc goes back to the table", async ({ page }) => {
  await page.goto(open(FIRST));
  const breadcrumb = page.getByRole("navigation", { name: "Breadcrumb" });
  await expect(breadcrumb).toContainText(episodeId(FIRST)); // keys only work once it's open

  await page.keyboard.press("j");
  await expect(breadcrumb).toContainText(episodeId(SECOND));
  await page.keyboard.press("k");
  await expect(breadcrumb).not.toContainText(episodeId(SECOND));
  await expect(breadcrumb).toContainText(episodeId(FIRST));
  await page.keyboard.press("Escape");

  await expect(page.getByRole("heading", { name: "Episodes" })).toBeVisible();
  await expect(page).toHaveURL(/\?page=episodes$/);
});

test("a disagreement on the Evaluation page opens its Workstation", async ({ page, request }) => {
  // SECOND needs review (its visual samples split, and placement has no exterior track), while
  // Spark alone's recorded answers reject it.
  await referenceLabel(request, [episodeId(SECOND)]);
  await page.goto("/?page=evaluation");

  const list = page.getByRole("table", { name: "Spark alone and Winnow disagree" });
  const row = list
    .getByRole("row")
    .filter({ has: page.getByRole("cell", { name: episodeId(SECOND), exact: true }) });
  await expect(row.getByTestId("triage-decision")).toHaveText(["Needs review", "Reject"]);
  await row.click();

  await expect(page).toHaveURL(new RegExp(`page=episodes&episode=droid_100%3A${String(SECOND)}`));
  await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toContainText(
    episodeId(SECOND),
  );
  await expect(page.getByLabel("Episode video")).toBeVisible();
});
