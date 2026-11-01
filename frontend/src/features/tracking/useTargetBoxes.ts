import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import type { components } from "../../api/schema";
import { datasetStatusKey } from "../dataset/useDatasetStatus";

export type TargetBox = components["schemas"]["TargetBox"];
export type FrameRect = components["schemas"]["FrameRect"];

export const targetBoxesKey = ["target-boxes"] as const;

/** Each boxed Episode's target box: the hand-drawn one if any, else SAM's. */
export function useTargetBoxes(enabled = true) {
  return useQuery({
    queryKey: targetBoxesKey,
    enabled,
    queryFn: async () => {
      const { data, response } = await api.GET("/api/target-boxes");
      if (!response.ok || !data) throw new Error(`Target boxes failed: ${String(response.status)}`);
      return data;
    },
  });
}

/** One Episode's target box, if it has one yet; none while `hidden` (Reference label mode). */
export function useTargetBox(episodeId: string, hidden = false): TargetBox | undefined {
  const fetched = useTargetBoxes(!hidden).data; // cached data outlives `enabled: false`
  return hidden ? undefined : fetched?.find((t) => t.episode_id === episodeId);
}

export function useDrawTargetBox() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ episodeId, rect }: { episodeId: string; rect: FrameRect }) => {
      const { data, error, response } = await api.PUT("/api/episodes/{episode_id}/target-box", {
        params: { path: { episode_id: episodeId } },
        body: rect,
      });
      if (!response.ok || !data) {
        const detail = (error as { detail?: unknown } | undefined)?.detail;
        throw new Error(typeof detail === "string" ? detail : "The target box couldn't be saved");
      }
      return data;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: targetBoxesKey }),
        queryClient.invalidateQueries({ queryKey: datasetStatusKey }),
      ]);
    },
  });
}
