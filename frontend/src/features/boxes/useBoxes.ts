import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import type { components } from "../../api/schema";
import { datasetStatusKey } from "../dataset/useDatasetStatus";
import { latestJobKey } from "../jobs/useLatestJob";

export type Box = components["schemas"]["Box"];
export type BoxDraw = components["schemas"]["BoxDraw"];
export type ExteriorCamera = BoxDraw["camera"];

const boxesKey = ["boxes"] as const;

export function useBoxes() {
  return useQuery({
    queryKey: boxesKey,
    queryFn: async () => {
      const { data, response } = await api.GET("/api/boxes");
      if (!response.ok || !data) throw new Error(`Boxes failed: ${String(response.status)}`);
      return data;
    },
  });
}

export function useSaveBox() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ episodeId, draw }: { episodeId: string; draw: BoxDraw }) => {
      const { data, error, response } = await api.PUT("/api/episodes/{episode_id}/box", {
        params: { path: { episode_id: episodeId } },
        body: draw,
      });
      if (!response.ok || !data) {
        const detail = (error as { detail?: unknown } | undefined)?.detail;
        throw new Error(typeof detail === "string" ? detail : "The box couldn't be saved");
      }
      return data;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: boxesKey }),
        queryClient.invalidateQueries({ queryKey: datasetStatusKey }),
        queryClient.invalidateQueries({ queryKey: latestJobKey("box") }), // the work it queued
      ]);
    },
  });
}

export function frame0Url(episodeId: string, camera: string): string {
  return `/api/episodes/${encodeURIComponent(episodeId)}/frame0/${camera}`;
}
