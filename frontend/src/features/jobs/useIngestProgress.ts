// The latest ingest job, refreshing what ingest changes (counts, Episodes, candidates, tracks) as its
// items land, so every page showing them stays current while a job runs.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { useLatestJob } from "./useLatestJob";

const CHANGED_BY_INGEST = [["dataset"], ["episodes"], ["selection"], ["tracks"], ["triage"]];

export function useIngestProgress() {
  const job = useLatestJob("ingest");
  const queryClient = useQueryClient();
  const settled = job.data ? job.data.done + job.data.failed : 0;

  useEffect(() => {
    for (const queryKey of CHANGED_BY_INGEST) void queryClient.invalidateQueries({ queryKey });
  }, [settled, queryClient]);

  return job;
}
