import { expect, test } from "@playwright/test";

import { boxEpisode, dragBox, EPISODES, episodeId, ingest, RECORDED_BOX } from "./helpers.ts";

// Its instruction is "Put the marker in the pot"; the fixture's views have no pot, so the
// recorded SAM finds none, while its exterior track follows the box in Exterior 2 (testsrc2).
const [INDEX] = EPISODES.targets;
const EPISODE = episodeId(INDEX);
const EXTERIOR_2 = "exterior_image_2_left";

test.beforeEach(async ({ request }) => {
  await ingest(request, EPISODES.targets);
  await boxEpisode(request, EPISODE, EXTERIOR_2);
});

test("Prepare shows the proposed target box, and a drawn one replaces it", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await page.goto("/?page=prepare");

  const card = page.getByTestId(`target-card-${EPISODE}`);
  await expect(card.getByTestId("target-status")).toHaveText("SAM found no “pot”");
  await expect(page.getByTestId("exterior-tracks")).not.toContainText("—");

  await card
    .getByRole("button", { name: `Draw the target box for Episode ${String(INDEX)}` })
    .click();
  const dialog = page.getByRole("dialog");
  await dragBox(page);
  await dialog.getByRole("button", { name: "Save target box" }).click();

  await expect(dialog).toHaveCount(0);
  await expect(card.getByTestId("target-status")).toHaveText("Hand-drawn");
  await expect(card.getByLabel("Target box", { exact: true })).toBeVisible();
  const targets = (await (await page.request.get("/api/target-boxes")).json()) as {
    episode_id: string;
    origin: string;
    box: { left: number; top: number; right: number; bottom: number };
  }[];
  const drawn = targets.find((t) => t.episode_id === EPISODE);
  expect(drawn?.origin).toBe("hand");
  expect(drawn?.box).toEqual({
    left: RECORDED_BOX.x1,
    top: RECORDED_BOX.y1,
    right: RECORDED_BOX.x2,
    bottom: RECORDED_BOX.y2,
  });
  expect(errors).toEqual([]);
});

test("the Workstation draws the exterior track and target box on the boxed view", async ({
  page,
  request,
}) => {
  const target = { x1: 20, y1: 20, x2: 80, y2: 60 };
  expect((await request.put(`/api/episodes/${EPISODE}/target-box`, { data: target })).ok()).toBe(
    true,
  );
  await page.goto(`/?page=episodes&episode=${encodeURIComponent(EPISODE)}&t=1`);

  await expect(page.getByTestId("target-status")).toHaveText("Hand-drawn");
  await expect(page.getByTestId("track-status-exterior")).toContainText("box on 15 of 15 frames");
  await expect(page.getByTestId("target-box")).toHaveCount(0); // Exterior 1 is showing
  await page.getByRole("tab", { name: "Exterior 2" }).click();
  await expect(page.getByTestId("target-box")).toBeVisible();
  await expect(page.getByLabel("exterior track box")).toBeVisible();
  await page.getByRole("tab", { name: "Wrist" }).click();
  await expect(page.getByTestId("target-box")).toHaveCount(0);
});
