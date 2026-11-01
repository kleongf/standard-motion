// The latest job a saved box queued (exterior track and target box), refreshing what it changes
// as its items land.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { useLatestJob } from "../jobs/useLatestJob";
import { targetBoxesKey } from "./useTargetBoxes";
import { tracksKey } from "./useTracks";

const CHANGED_BY_BOX_JOBS = [["dataset"], tracksKey, targetBoxesKey];

export function useBoxJobProgress() {
  const job = useLatestJob("box");
  const queryClient = useQueryClient();
  const settled = job.data ? job.data.done + job.data.failed : 0;

  useEffect(() => {
    for (const queryKey of CHANGED_BY_BOX_JOBS) void queryClient.invalidateQueries({ queryKey });
  }, [settled, queryClient]);

  return job;
}
