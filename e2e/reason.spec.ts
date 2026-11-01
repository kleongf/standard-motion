import { expect, test, type APIRequestContext } from "@playwright/test";

import { EPISODES, episodeId, ingest, referenceLabel } from "./helpers.ts";

// The spec's Episode is rejected for two failed grasp attempts before its grasp. Spark's Reason
// for it is scripted (backend/tests/record_reason.py); every other Episode's Reason call misses
// the replay and keeps its template Reason.
const [REASON] = EPISODES.reason;
const id = episodeId(REASON);
const WRITTEN =
  "The gripper closed on nothing at 0.9 s and again at 1.3 s, only holding the object from " +
  "1.8 s, so it wasn't grasped on the first try.";

/** Queue Spark's Reasons and wait until this spec's Episode has its own. Another spec's visual
 * job may have queued it already, in which case there's nothing left to queue. */
async function writeReason(request: APIRequestContext): Promise<void> {
  const started = await request.post("/api/reasons");
  expect(started.status()).toBe(202);
  await expect
    .poll(
      async () => {
        const triage = (await (
          await request.get(`/api/episodes/${encodeURIComponent(id)}/triage`)
        ).json()) as { reason_source?: string };
        return triage.reason_source;
      },
      { timeout: 30_000 },
    )
    .toBe("spark");
}

test.beforeEach(async ({ request }) => {
  await ingest(request, EPISODES.reason);
  await referenceLabel(request, [id]);
});

test("the Workstation shows Spark's Reason, marked, and its times seek", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await writeReason(request);

  await page.goto(`/?page=episodes&episode=${encodeURIComponent(id)}`);

  await expect(page.getByTestId("triage-decision")).toHaveText("Reject");
  await expect(page.getByTestId("reason-source")).toHaveText("written by Spark");
  const reason = page.getByTestId("reason");
  await expect(reason).toHaveText(WRITTEN);
  await reason.getByRole("button", { name: "1.3 s" }).click();
  await expect(page.getByText("1.3 / 3.0 s")).toBeVisible();
  expect(errors).toEqual([]);
});
