// The draft's dry run as it goes: each answer Spark gives on the anchor pool refreshes the draft's
// preview, so a visual Criterion's pass rate shows without pressing Run.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import type { components } from "../../api/schema";
import { latestJobKey, useLatestJob } from "../jobs/useLatestJob";
import { DRY_RUN } from "./dryRun";
import { draftKey, type RubricDraft, underDraft } from "./useDraft";

type Job = components["schemas"]["Job"];

/** Which dry run, and how many of its items changed what the preview shows: Spark's answers, and
 * failures, which each step records against its Criterion. A clip cut is neither. */
function answered(job: Job | null | undefined): string {
  if (!job) return "none";
  const told = job.items.filter(
    (item) => item.status === "failed" || (item.status === "done" && item.step === "visual"),
  );
  return `${String(job.id)}:${String(told.length)}`;
}

/** The latest dry run, looked up again whenever the draft changes: a compile, a card edit or an
 * interview answer may have queued one. */
export function useDryRun(draft: RubricDraft | null | undefined) {
  const queryClient = useQueryClient();
  const job = useLatestJob(DRY_RUN);
  const shown = useRef(draft);
  useEffect(() => {
    const before = shown.current;
    shown.current = draft;
    // The draft as the page opened, or first loading, queued nothing new: useLatestJob is
    // fetching the latest already.
    if (before === draft || before === undefined) return;
    void queryClient.invalidateQueries({ queryKey: latestJobKey(DRY_RUN) });
  }, [draft, queryClient]);

  // What the dry run has answered, as last seen: a change means new answers to preview. A dry
  // run seen first already finished was answered when the page's preview was read; one still
  // running may have answered since.
  const told = answered(job.data);
  const running = job.data?.finished === false;
  const seen = useRef<string | null>(null);
  useEffect(() => {
    if (!job.isSuccess) return;
    const changed = seen.current === null ? running : seen.current !== told;
    seen.current = told;
    if (changed) void queryClient.invalidateQueries({ queryKey: draftKey, predicate: underDraft });
  }, [job.isSuccess, told, running, queryClient]);

  return job.data;
}
