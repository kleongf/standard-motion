import { expect, type APIRequestContext, type Locator, type Page } from "@playwright/test";

/** The fixture Episodes each spec owns. Every spec shares one e2e server, whose Reference labels,
 * sets and boxes are permanent, so a spec ingests, labels, boxes, adds to a set and asserts on
 * only its own Episodes; that way each passes alone and in any order. A new spec claims unused
 * indices here; past the last one, raise `--episodes` in scripts/e2e-server.ts and E2E_EPISODES
 * in backend/tests/record_meta.py, and re-record.
 *
 * Fixture Episode i depends on i % 3: 0 grasps cleanly ("Put the marker in the pot"); 1 releases
 * inside the release height's margin, less confidently when i % 6 == 4 ("Move the black remote
 * control to the left"); 2 is rejected after two failed grasp attempts, with no instruction and a
 * failing Dataset outcome. Unboxed, every Episode that isn't rejected needs review: placement has
 * no exterior track. Boxed in Exterior 2 with PLACED_TARGET drawn (`boxForPlacement`), Episodes
 * 0, 1, 3, 4, 6, 12, 15, 16 and 18 have a healthy recorded track, so i % 3 == 0 is kept; the
 * rest have none to speak of (17's is unchecked), so their placement is unsure with "track
 * lost". */
export const EPISODES = {
  workstation: [9, 10],
  referenceLabels: [2],
  targets: [3],
  awaitingLabel: [7],
  testSetEvaluation: [5],
  sets: [6],
  triage: [1, 8, 0, 4],
  boxes: [11, 12, 13],
  prepare: [14, 17],
  review: [16],
  audit: [15, 18],
  voice: [19],
  reason: [20],
  quality: [22, 23],
} as const;

export function episodeId(index: number): string {
  return `droid_100:${String(index)}`;
}

/** The e2e Dev set, which is also the anchor pool: the sets spec's Episode, frozen. Compile's
 * recorded reply (backend/tests/record_meta.py, E2E_DEV_SET) was made against exactly it, so a
 * spec that compiles calls this first. */
export const DEV_SET = EPISODES.sets;

/** Ingest the Dev set's Episodes, define and freeze it unless that's done, and give them their
 * Reference labels: the Describe page counts only labelled anchor Episodes. */
export async function freezeDevSet(request: APIRequestContext): Promise<void> {
  await ingest(request, DEV_SET);
  await referenceLabel(request, DEV_SET.map(episodeId));
  const sets = (await (await request.get("/api/sets")).json()) as {
    name: string;
    frozen_at: string | null;
  }[];
  if (sets.find((s) => s.name === "dev")?.frozen_at === null) {
    await request.post("/api/sets/dev/episodes", { data: { episode_ids: DEV_SET.map(episodeId) } });
    // Forced: the fixture Dev set holds none of the real Dev set's already-seen Episodes.
    await request.post("/api/sets/dev/freeze", { data: { force: true } });
  }
}

/** Give each Episode a first-pass Reference label passing every Phrase, which reveals its
 * Triage decision. Labels never change, so one already there is kept. */
export async function referenceLabel(
  request: APIRequestContext,
  episodeIds: string[],
): Promise<void> {
  const description = (await (await request.get("/api/reference-labels/description")).json()) as {
    phrases: string[];
  };
  const phrases = description.phrases.map((phrase) => ({ phrase, passed: true, interval: null }));
  for (const id of episodeIds) {
    const saved = await request.post(`/api/episodes/${encodeURIComponent(id)}/reference-labels`, {
      data: { phrases, elapsed_s: 10, instruction: "Put the block in the bowl" },
    });
    expect([201, 409]).toContain(saved.status());
  }
}

/** Open the Describe composer on the Description. With a draft, the composer is a chat with Spark
 * until "Edit the Description" opens the Description in it. */
export async function openDescription(page: Page): Promise<void> {
  const box = page.getByRole("textbox", { name: /^(Description|Message Spark)$/ });
  await expect(box).toBeVisible();
  if ((await box.getAttribute("aria-label")) === "Message Spark") {
    await page.getByRole("button", { name: "Edit the Description" }).first().click();
  }
  await expect(page.getByLabel("Description", { exact: true })).toBeVisible();
}

/** Click Compile on the Describe page, its Description box holding `description`. When the draft
 * already has that Description (another spec may have left it), compiling starts the draft
 * afresh, which asks first: confirm it. */
export async function clickCompile(
  page: Page,
  request: APIRequestContext,
  description: string,
): Promise<void> {
  const draft = (await (await request.get("/api/rubric/draft")).json()) as {
    description: string;
  } | null;
  await page.getByRole("button", { name: "Compile" }).click();
  if (draft?.description === description) {
    const afresh = page.getByRole("alertdialog", { name: "Start the draft afresh?" });
    await afresh.getByRole("button", { name: "Start afresh" }).click();
  }
}

/** Ingest fixture Episodes through the API and wait for the job to finish. */
export async function ingest(
  request: APIRequestContext,
  indices: readonly number[],
): Promise<void> {
  const started = await request.post("/api/episodes/ingest", {
    data: { source: "droid_100", indices },
  });
  const { job_id: jobId } = (await started.json()) as { job_id: number };
  await expect
    .poll(
      async () => {
        const job = (await (await request.get(`/api/jobs/${String(jobId)}`)).json()) as {
          finished: boolean;
        };
        return job.finished;
      },
      { timeout: 30_000 },
    )
    .toBe(true);
}

/** Ask the latest Rubric's visual Criteria of these Episodes and wait. Their answers are scripted
 * for every unboxed fixture Episode (backend/tests/record_visual.py); a boxed one's clip is cut
 * differently, so its visual Criteria fail their step and stay unsure. */
export async function askVisual(
  request: APIRequestContext,
  indices: readonly number[],
): Promise<void> {
  const started = await request.post("/api/visual/ask", {
    data: { episode_ids: indices.map(episodeId) },
  });
  expect(started.status()).toBe(202);
  const { job_id: jobId } = (await started.json()) as { job_id: number | null };
  if (jobId === null) return;
  await expect
    .poll(
      async () => {
        const job = (await (await request.get(`/api/jobs/${String(jobId)}`)).json()) as {
          finished: boolean;
        };
        return job.finished;
      },
      { timeout: 30_000 },
    )
    .toBe(true);
}

/** The box `dragBox` draws: from 40% to 60% of each side of the 320x180 frame. Its exterior
 * track and target box are recorded for every fixture Episode in both exterior views
 * (backend/tests/record_meta.py), so the work a saved box queues replays. */
export const RECORDED_BOX = { x1: 128, y1: 72, x2: 192, y2: 108 };

/** Drag RECORDED_BOX on the box canvas. Each corner is aimed a quarter frame pixel inside the
 * one wanted, so the browser rounding the pointer to a whole CSS pixel can't move it. */
export async function dragBox(page: Page): Promise<void> {
  const canvas = page.getByTestId("box-canvas");
  const frame = canvas.getByRole("img", { name: "Frame 0" });
  await expect.poll(() => frame.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(320);
  // Wait out the dialog's opening zoom, or the canvas is measured mid-zoom.
  await canvas.evaluate((el) => {
    const dialog = el.closest("[role=dialog]") ?? el;
    return Promise.all(dialog.getAnimations({ subtree: true }).map((a) => a.finished));
  });
  const bounds = await canvas.boundingBox();
  if (!bounds) throw new Error("box canvas has no size");
  const at = (x: number, y: number) =>
    [
      bounds.x + ((x + 0.25) / 320) * bounds.width,
      bounds.y + ((y + 0.25) / 180) * bounds.height,
    ] as const;
  const { x1, y1, x2, y2 } = RECORDED_BOX;
  await page.mouse.move(...at(x1, y1));
  await page.mouse.down();
  await page.mouse.move(...at(x2, y2), { steps: 4 });
  await page.mouse.up();
}

/** A target box drawn around where the recorded Exterior 2 tracks end, so placement passes on
 * Episodes whose track is healthy. */
export const PLACED_TARGET = { x1: 100, y1: 0, x2: 230, y2: 180 };

/** Box an Episode in Exterior 2 and draw PLACED_TARGET, so its tracked Criteria are scored. */
export async function boxForPlacement(request: APIRequestContext, episodeId: string) {
  await boxEpisode(request, episodeId, "exterior_image_2_left");
  const drawn = await request.put(`/api/episodes/${encodeURIComponent(episodeId)}/target-box`, {
    data: PLACED_TARGET,
  });
  expect(drawn.ok()).toBe(true);
}

/** Box an Episode's object through the API and wait for the work the box queues. */
export async function boxEpisode(
  request: APIRequestContext,
  episodeId: string,
  camera: string,
): Promise<void> {
  const saved = await request.put(`/api/episodes/${encodeURIComponent(episodeId)}/box`, {
    data: { camera, ...RECORDED_BOX },
  });
  expect(saved.ok()).toBe(true);
  await expect
    .poll(async () => {
      const job = (await (await request.get("/api/jobs/latest?kind=box")).json()) as {
        finished: boolean;
      };
      return job.finished;
    })
    .toBe(true);
}

/** The frozen Description, whose compile against the Dev set is recorded
 * (backend/tests/record_meta.py): the describe specs compile it, and leave it compiled. */
export const FROZEN =
  "Expert pick-and-place: grasps the object on the first try, never drops it, places it in or " +
  "on the target named in the instruction, no long pauses.";

/** Undo every interview answer, latest first, withdrawing the labels they left. */
export async function undoInterview(request: APIRequestContext): Promise<void> {
  const interview = (await (await request.get("/api/interview")).json()) as {
    answered: { id: number }[];
  };
  for (const { id } of [...interview.answered].reverse()) {
    await request.delete(`/api/interview/answers/${String(id)}`);
  }
}

/** Skip each interview question until one of `kind` (its card's label) is asked. */
export async function skipTo(question: Locator, kind: string): Promise<void> {
  for (let i = 0; i < 20; i++) {
    const asked = (await question.textContent()) ?? "";
    if (asked.startsWith(kind)) return;
    await question.getByRole("button", { name: /^Skip/ }).click();
    await expect(question).not.toHaveText(asked); // the next question is up
  }
  throw new Error(`No ${kind} question`);
}
