import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import type { components } from "../../api/schema";
import { triageKey } from "../triage/useTriage";

export type ReferenceLabel = components["schemas"]["ReferenceLabel"];
export type ReferenceLabelDraw = components["schemas"]["ReferenceLabelDraw"];

const labelsKey = ["reference-labels"] as const;

export function useReferenceLabels() {
  return useQuery({
    queryKey: labelsKey,
    queryFn: async () => {
      const { data, response } = await api.GET("/api/reference-labels");
      if (!response.ok || !data)
        throw new Error(`Reference labels failed: ${String(response.status)}`);
      return data;
    },
  });
}

export function useFrozenDescription() {
  return useQuery({
    queryKey: [...labelsKey, "description"],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/reference-labels/description");
      if (!response.ok || !data) throw new Error(`Description failed: ${String(response.status)}`);
      return data;
    },
    staleTime: Infinity, // frozen
  });
}

export function useSaveReferenceLabel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ episodeId, draw }: { episodeId: string; draw: ReferenceLabelDraw }) => {
      const { data, error, response } = await api.POST(
        "/api/episodes/{episode_id}/reference-labels",
        { params: { path: { episode_id: episodeId } }, body: draw },
      );
      if (!response.ok || !data) {
        const detail = (error as { detail?: unknown } | undefined)?.detail;
        throw new Error(typeof detail === "string" ? detail : "The label couldn't be saved");
      }
      return data;
    },
    onSuccess: async () => {
      // Labelling reveals the Episode's Dataset outcome, its Triage decision and any
      // instruction just written.
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: labelsKey }),
        queryClient.invalidateQueries({ queryKey: ["episodes"], exact: true }),
        queryClient.invalidateQueries({ queryKey: triageKey }),
      ]);
    },
  });
}

/** Episodes with a label for this pass. */
export function labelledIds(labels: ReferenceLabel[] | undefined, relabel: boolean): Set<string> {
  return new Set((labels ?? []).filter((l) => l.relabel === relabel).map((l) => l.episode_id));
}
