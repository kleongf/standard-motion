import { useIsMutating, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import type { components } from "../../api/schema";

export type RubricDraft = components["schemas"]["RubricDraft"];
export type DraftPhrase = components["schemas"]["DraftPhrase"];
export type Criterion = components["schemas"]["Criterion"];
export type Setting = components["schemas"]["Setting"];
export type PhraseStatus = DraftPhrase["status"];

export const draftKey = ["rubric", "draft"] as const;

/** What is keyed under the draft (its preview, the interview), not the draft itself. */
export function underDraft(query: { queryKey: readonly unknown[] }): boolean {
  return query.queryKey.length > draftKey.length;
}
const anchorPoolKey = ["anchor-pool"] as const;
const compileKey = ["compile"] as const;

/** The Rubric draft on the Describe page; null until a Description is compiled. */
export function useDraft() {
  return useQuery({
    queryKey: draftKey,
    queryFn: async () => {
      const { data, response } = await api.GET("/api/rubric/draft");
      if (!response.ok) throw new Error(`Draft failed: ${String(response.status)}`);
      return data ?? null;
    },
  });
}

/** Compile a Description into the draft: one Spark call, so it takes a while. An edit of the
 * draft's Description compiles only the changed Phrases, and the interview goes on. */
export function useCompile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: compileKey,
    mutationFn: async (description: string) => {
      const { data, error, response } = await api.POST("/api/rubric/draft/compile", {
        body: { description, fresh: false },
      });
      if (!response.ok || !data) {
        const detail = (error as { detail?: unknown } | undefined)?.detail;
        throw new Error(typeof detail === "string" ? detail : "The Description couldn't compile");
      }
      return data;
    },
    onSuccess: async (draft) => {
      queryClient.setQueryData(draftKey, draft);
      // A new draft re-sorts the anchor pool and changes the interview: a compile afresh starts a
      // new one, a recompile carries over the answers about text it left alone. Refetch both.
      await queryClient.invalidateQueries({ queryKey: draftKey, predicate: underDraft });
    },
  });
}

/** Whether a compile is under way, wherever on the page it was started. */
export function useCompiling(): boolean {
  return useIsMutating({ mutationKey: compileKey }) > 0;
}

/** The Episodes the Rubric is written against: the Dev set, never the Test set. */
export function useAnchorPool() {
  return useQuery({
    queryKey: anchorPoolKey,
    queryFn: async () => {
      const { data, response } = await api.GET("/api/anchor-pool");
      if (!response.ok || !data) throw new Error(`Anchor pool failed: ${String(response.status)}`);
      return data;
    },
  });
}
