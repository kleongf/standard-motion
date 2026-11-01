import { resolve } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { EPISODES, episodeId, ingest, referenceLabel } from "./helpers.ts";

// Chromium's fake microphone plays this file, which says what backend/tests/record_voice.py
// scripts Voice Transcribe to hear; replay answers any captured audio with that transcript, and
// Spark's mapping of it is scripted there too.
const FAKE_MIC = resolve("e2e", "fixtures", "voice-turn.wav");
test.use({
  launchOptions: {
    args: [
      "--use-fake-ui-for-media-stream",
      "--use-fake-device-for-media-stream",
      `--use-file-for-fake-audio-capture=${FAKE_MIC}`,
    ],
  },
  permissions: ["microphone"],
});

// Like the review spec's, it releases inside the release height's margin and is never boxed, so
// it needs review on "never drops it" and on placement.
const [SPOKEN] = EPISODES.voice;
const ID = episodeId(SPOKEN);
const NEVER_DROPS = "never drops it";

test.beforeEach(async ({ request }) => {
  await ingest(request, EPISODES.voice);
  await referenceLabel(request, [ID]);
});

/** One push-to-talk turn on V, which counts once the microphone is live; resolves when its
 * POST /voice has answered. */
async function speak(page: Page) {
  const heard = page.waitForResponse(
    (r) => r.request().method() === "POST" && r.url().endsWith("/voice"),
  );
  const voice = page.getByRole("region", { name: "Voice" });
  await page.keyboard.down("v");
  // "Listening" waits for the microphone's first audio: only then does the hold count.
  await expect(voice.getByRole("button", { name: /Listening/ })).toBeVisible();
  await page.waitForTimeout(1500); // talk: a turn under 0.3 s isn't sent
  await page.keyboard.up("v");
  expect((await heard).ok()).toBe(true);
}

test("a confirmed chip from a spoken turn takes the Episode out of the queue", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await page.goto(`/?page=review&episode=${encodeURIComponent(ID)}`);
  const current = page.getByTestId("review-current");
  await expect(current).toContainText(ID);
  // The panel shows once health says Meta (here, its replay) can hear a turn.
  const voice = page.getByRole("region", { name: "Voice" });
  await expect(voice).toBeVisible();

  await speak(page);

  await expect(voice.getByTestId("voice-heard")).toContainText("It drops the marker right here");
  await expect(voice.getByRole("alert")).toHaveCount(0);
  // The microphone stays open between turns: the next press records on it at once.
  await expect(voice.getByTestId("mic-on")).toBeVisible();
  await speak(page);
  await expect(voice.getByRole("alert")).toHaveCount(0);
  const chip = voice.getByRole("group", { name: NEVER_DROPS });
  await expect(chip).toContainText("Fail");
  await expect(chip).toContainText("“It drops the marker right here”");
  await expect(chip.getByRole("button", { name: /^Seek to \d+\.\d s$/ })).toBeVisible();
  // Nothing is saved until the chip is confirmed.
  await expect(current).toContainText(ID);
  await chip.getByRole("button", { name: "Confirm" }).click();

  await expect(current.filter({ hasText: ID })).toHaveCount(0);
  const upNext = page.getByRole("region", { name: "Up next" });
  await expect(upNext.getByRole("button", { name: new RegExp(ID) })).toHaveCount(0);
  await page.goto(`/?page=episodes&episode=${encodeURIComponent(ID)}`);
  await expect(page.getByTestId("reason")).toHaveText(
    `Rejected: "${NEVER_DROPS}" was marked fail in review.`,
  );
  expect(errors).toEqual([]);
});
