import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import type { components } from "../../api/schema";
import { useSaveLabel } from "../labels/useLabels";

export type AuditSample = components["schemas"]["AuditSample"];
export type AuditItem = components["schemas"]["AuditItem"];
export type KeepPrecision = components["schemas"]["KeepPrecision"];

export const auditKey = ["audit"] as const;

/** The latest Rubric version's Audit sample, each item's mark, and Keep precision. */
export function useAudit() {
  return useQuery({
    queryKey: auditKey,
    queryFn: async () => {
      const { data, response } = await api.GET("/api/audit");
      if (!response.ok || !data) throw new Error(`Audit failed: ${String(response.status)}`);
      return data;
    },
  });
}

/** Draw the sample; once drawn for a Rubric version and margin multiplier s, drawing again
 * returns the same one. */
export function useDrawSample() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.POST("/api/audit/sample", { body: {} });
      if (!response.ok || !data) {
        const detail = (error as { detail?: unknown } | undefined)?.detail;
        throw new Error(typeof detail === "string" ? detail : "The sample couldn't be drawn");
      }
      return data;
    },
    onSuccess: (sample) => {
      queryClient.setQueryData(auditKey, sample);
    },
  });
}

/** Mark an item Good (an `audit` pass on every Phrase) or Bad (an `audit` fail on the one that
 * fails). Scoring never reads these labels, so no Triage decision changes. */
export function useMarkItem() {
  const queryClient = useQueryClient();
  const save = useSaveLabel();
  return useMutation({
    mutationFn: async (mark: { episodeId: string; value: "pass" | "fail"; phrases: string[] }) => {
      for (const phrase of mark.phrases) {
        const draw = { phrase, value: mark.value, source: "audit" as const };
        await save.mutateAsync({ episodeId: mark.episodeId, draw });
      }
    },
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: auditKey });
    },
  });
}
