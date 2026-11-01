import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import type { components } from "../../api/schema";
import { reviewKey } from "../review/useReview";
import { triageKey } from "../triage/useTriage";

export type LabelDraw = components["schemas"]["LabelDraw"];

/** Save a pass or fail on one Phrase of one Episode; it overrides that Phrase's result. */
export function useSaveLabel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ episodeId, draw }: { episodeId: string; draw: LabelDraw }) => {
      const { data, error, response } = await api.POST("/api/episodes/{episode_id}/labels", {
        params: { path: { episode_id: episodeId } },
        body: draw,
      });
      if (!response.ok || !data) {
        const detail = (error as { detail?: unknown } | undefined)?.detail;
        throw new Error(typeof detail === "string" ? detail : "The label couldn't be saved");
      }
      return data;
    },
    onSuccess: async () => {
      // The Triage decision recomputes, so the Episode may leave the queue.
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: triageKey }),
        queryClient.invalidateQueries({ queryKey: reviewKey }),
      ]);
    },
  });
}
