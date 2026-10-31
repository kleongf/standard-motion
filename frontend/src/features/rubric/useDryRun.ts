// The draft's dry run as it goes: each answer Spark gives on the anchor pool refreshes the draft's
// preview, so a visual Criterion's pass rate shows without pressing Run.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { latestJobKey, useLatestJob } from "../jobs/useLatestJob";
import { DRY_RUN } from "./dryRun";
import { draftKey, type RubricDraft, underDraft } from "./useDraft";

/** The latest dry run, refetched whenever the draft changes: a compile, a card edit or an
 * interview answer may have queued one. */
export function useDryRun(draft: RubricDraft | null | undefined) {
  const queryClient = useQueryClient();
  const job = useLatestJob(DRY_RUN);
  useEffect(() => {
    void queryClient.invalidateQueries({ queryKey: latestJobKey(DRY_RUN) });
  }, [draft, queryClient]);

  // Which dry run, and how much of it has settled, as last seen: a change means new answers to
  // preview. The first sight sets the baseline, as the page's preview was read alongside it.
  const data = job.data;
  const settled = data ? `${String(data.id)}:${String(data.done + data.failed)}` : "none";
  const seen = useRef<string | null>(null);
  useEffect(() => {
    if (!job.isSuccess) return;
    const changed = seen.current !== null && seen.current !== settled;
    seen.current = settled;
    if (changed) void queryClient.invalidateQueries({ queryKey: draftKey, predicate: underDraft });
  }, [job.isSuccess, settled, queryClient]);

  return job.data;
}
