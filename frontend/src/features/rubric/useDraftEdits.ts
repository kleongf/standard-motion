import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import type { components } from "../../api/schema";
import { triageKey } from "../triage/useTriage";
import { draftKey, underDraft } from "./useDraft";
import { rubricKey, versionsKey } from "./useRubric";

export type DraftEdit = components["schemas"]["DraftEdit"];
export type AnchorPreview = components["schemas"]["AnchorPreview"];
export type CriterionPreview = components["schemas"]["CriterionPreview"];

const previewKey = [...draftKey, "preview"] as const;

export function failure(error: unknown, fallback: string): Error {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  return new Error(typeof detail === "string" ? detail : fallback);
}

/** The draft, with `edit` applied but not saved, scored on the anchor pool: no model call, so
 * it follows a threshold drag. Keeps showing the last numbers while the next ones load. */
export function useDraftPreview(edit: DraftEdit, enabled: boolean) {
  return useQuery({
    queryKey: [...previewKey, edit],
    enabled,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, response } = await api.POST("/api/rubric/draft/preview", { body: edit });
      if (!response.ok || !data) throw new Error(`Preview failed: ${String(response.status)}`);
      return data;
    },
  });
}

/** A frozen Rubric version scored on the anchor pool. */
export function useVersionPreview(version: number | null) {
  return useQuery({
    queryKey: [...rubricKey, "versions", version, "preview"],
    enabled: version !== null,
    queryFn: async () => {
      const { data, response } = await api.GET("/api/rubric/versions/{version}/preview", {
        params: { path: { version: version ?? 0 } },
      });
      if (!response.ok || !data) throw new Error(`Preview failed: ${String(response.status)}`);
      return data;
    },
  });
}

/** Save direct edits to the draft: thresholds, hard/soft, on/off, the Rubric settings. */
export function useEditDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (edit: DraftEdit) => {
      const { data, error, response } = await api.PATCH("/api/rubric/draft", { body: edit });
      if (!response.ok || !data) throw failure(error, "The edit couldn't be saved");
      return data;
    },
    onSuccess: async (draft) => {
      queryClient.setQueryData(draftKey, draft);
      // It re-sorts the preview, and may change what the interview asks.
      await queryClient.invalidateQueries({ queryKey: draftKey, predicate: underDraft });
    },
  });
}

/** Freeze the draft into the next Rubric version, which every Episode is then scored against. */
export function useRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.POST("/api/rubric/draft/run");
      if (!response.ok || !data) throw failure(error, "Run failed");
      return data;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: rubricKey, exact: true }),
        queryClient.invalidateQueries({ queryKey: versionsKey }),
        queryClient.invalidateQueries({ queryKey: triageKey }),
      ]);
    },
  });
}
