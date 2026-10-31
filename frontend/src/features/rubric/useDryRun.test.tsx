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

afterEach(() => {
  vi.unstubAllGlobals();
});

function job(id: number, done: number, total = 2): Job {
  return {
    id,
    kind: DRY_RUN,
    created_at: "2026-10-31T00:00:00Z",
    total,
    queued: total - done,
    running: 0,
    done,
    failed: 0,
    finished: done === total,
    items: [],
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

test("refetches the draft's preview as the dry run's answers come in", async () => {
  const latest = { job: job(1, 0) };
  fakeBackend(latest);
  const { result, client, previews } = renderDryRun(DRAFT);
  await waitFor(() => {
    expect(result.current?.id).toBe(1);
  });
  const before = previews.count;

  client.setQueryData(latestJobKey(DRY_RUN), job(1, 1)); // a poll finds one answer in

  await waitFor(() => {
    expect(previews.count).toBe(before + 1);
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

  latest.job = job(1, 2); // the compile queued it, and replayed answers finished it at once
  rerender({ draft: { ...DRAFT, description: "Neat place, upright" } });

  await waitFor(() => {
    expect(result.current?.id).toBe(1);
  });
  await waitFor(() => {
    expect(previews.count).toBe(before + 1);
  });
});

test("a dry run already finished on opening the page refetches nothing", async () => {
  fakeBackend({ job: job(1, 2) });
  const { result, previews } = renderDryRun(DRAFT);
  await waitFor(() => {
    expect(result.current?.id).toBe(1);
  });
  await new Promise((resolve) => setTimeout(resolve, 50));

  expect(previews.count).toBe(1);
});
