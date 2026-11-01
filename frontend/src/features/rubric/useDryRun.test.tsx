import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, test, vi } from "vitest";

import type { components } from "../../api/schema";
import { latestJobKey } from "../jobs/useLatestJob";
import { DRY_RUN } from "./dryRun";
import { draftKey, type RubricDraft } from "./useDraft";
import { useDryRun } from "./useDryRun";

type Job = components["schemas"]["Job"];
type Status = components["schemas"]["JobItem"]["status"];

afterEach(() => {
  vi.unstubAllGlobals();
});

/** A dry run of one anchor Episode and visual Criterion: a crop, then a visual item. */
function job(id: number, crop: Status, visual: Status): Job {
  const items = [crop, visual].map((status, position) => ({
    position,
    step: position === 0 ? "crop" : "visual",
    label: "droid_100:6 ask-video",
    status,
    detail: null,
  }));
  const count = (status: Status) => items.filter((item) => item.status === status).length;
  return {
    id,
    kind: DRY_RUN,
    created_at: "2026-10-31T00:00:00Z",
    total: 2,
    queued: count("queued"),
    running: count("running"),
    done: count("done"),
    failed: count("failed"),
    finished: count("queued") + count("running") === 0,
    items,
  };
}

/** The backend, whose latest dry run is `latest.job`. */
function fakeBackend(latest: { job: Job | null }) {
  vi.stubGlobal(
    "fetch",
    vi.fn((request: Request) =>
      Promise.resolve(
        new URL(request.url).pathname === "/api/jobs/latest"
          ? Response.json(latest.job)
          : new Response(null, { status: 404 }),
      ),
    ),
  );
}

/** The hook beside a draft preview, as on the Describe page, counting each time it's read. */
function renderDryRun(draft: RubricDraft) {
  const previews = { count: 0 };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = (props: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{props.children}</QueryClientProvider>
  );
  const rendered = renderHook(
    (props: { draft: RubricDraft }) => {
      useQuery({
        queryKey: [...draftKey, "preview"],
        queryFn: () => ++previews.count,
      });
      return useDryRun(props.draft);
    },
    { wrapper, initialProps: { draft } },
  );
  return { ...rendered, client, previews };
}

const DRAFT = { description: "Neat place" } as RubricDraft;

test("refetches the draft's preview as Spark's answers come in, not as clips are cut", async () => {
  fakeBackend({ job: job(1, "running", "queued") });
  const { client, previews } = renderDryRun(DRAFT);
  await waitFor(() => {
    expect(previews.count).toBe(2); // read on opening, and again on first sight of the dry run
  });

  client.setQueryData(latestJobKey(DRY_RUN), job(1, "done", "running")); // a clip, no answer
  await new Promise((resolve) => setTimeout(resolve, 50));
  expect(previews.count).toBe(2);

  client.setQueryData(latestJobKey(DRY_RUN), job(1, "done", "done")); // Spark answered
  await waitFor(() => {
    expect(previews.count).toBe(3);
  });
});

test("a clip that couldn't be cut refetches the preview: it says why Spark wasn't asked", async () => {
  fakeBackend({ job: job(1, "running", "queued") });
  const { client, previews } = renderDryRun(DRAFT);
  await waitFor(() => {
    expect(previews.count).toBe(2);
  });

  client.setQueryData(latestJobKey(DRY_RUN), job(1, "failed", "failed"));

  await waitFor(() => {
    expect(previews.count).toBe(3);
  });
});

test("a new draft looks for the dry run it queued, and refetches the preview once it's in", async () => {
  const latest: { job: Job | null } = { job: null };
  fakeBackend(latest);
  const { result, rerender, previews } = renderDryRun(DRAFT);
  await waitFor(() => {
    expect(result.current).toBeNull();
  });
  const before = previews.count;

  latest.job = job(1, "done", "done"); // the compile queued it, and replay finished it at once
  rerender({ draft: { ...DRAFT, description: "Neat place, upright" } });

  await waitFor(() => {
    expect(result.current?.id).toBe(1);
  });
  await waitFor(() => {
    expect(previews.count).toBe(before + 1);
  });
});

test("a dry run already finished on opening the page refetches nothing", async () => {
  fakeBackend({ job: job(1, "done", "done") });
  const { result, previews } = renderDryRun(DRAFT);
  await waitFor(() => {
    expect(result.current?.id).toBe(1);
  });
  await new Promise((resolve) => setTimeout(resolve, 50));

  expect(previews.count).toBe(1);
});
