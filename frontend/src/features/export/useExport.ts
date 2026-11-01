// The export's data: its preview for a choice of what to include, the exports written so far,
// and starting one. Only the Reference-labelled Episodes' decisions are counted; the rest stay
// hidden until exported.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

import { api } from "../../api/client";
import type { components } from "../../api/schema";
import { latestJobKey } from "../jobs/useLatestJob";

export type Include = components["schemas"]["ExportRequest"]["include"];
export type ExportPreview = components["schemas"]["ExportPreview"];
export type SourceCounts = components["schemas"]["SourceCounts"];
export type PastExport = components["schemas"]["PastExport"];

const PAST_KEY = ["export", "past"] as const;

export function useExportPreview(include: Include) {
  return useQuery({
    queryKey: ["export", "preview", include],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/export/preview", {
        params: { query: { include } },
      });
      if (!response.ok || !data)
        throw new Error(`Export preview failed: ${String(response.status)}`);
      return data;
    },
  });
}

export function usePastExports() {
  return useQuery({
    queryKey: PAST_KEY,
    queryFn: async () => {
      const { data, response } = await api.GET("/api/export/past");
      if (!response.ok || !data) throw new Error(`Past exports failed: ${String(response.status)}`);
      return data;
    },
  });
}

/** Refetch the past exports once an export finishes. */
export function useRefreshPastExports() {
  const queryClient = useQueryClient();
  return useCallback(() => queryClient.invalidateQueries({ queryKey: PAST_KEY }), [queryClient]);
}

export function useStartExport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (include: Include) => {
      const { data, response } = await api.POST("/api/export", { body: { include } });
      if (!response.ok || !data)
        throw new Error(`Export failed to start: ${String(response.status)}`);
      return data.job_id;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: latestJobKey("export") }),
  });
}
