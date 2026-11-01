import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import type { components } from "../../api/schema";
import { auditKey } from "../audit/useAudit";
import { navigate } from "../core/url";
import { failure } from "../rubric/useDraftEdits";
import { reviewKey } from "../review/useReview";
import { rubricKey } from "../rubric/useRubric";
import { triageKey } from "../triage/useTriage";

export type Calibration = components["schemas"]["Calibration"];
export type CalibrationRecord = components["schemas"]["CalibrationRecord"];
export type ThresholdSuggestion = components["schemas"]["ThresholdSuggestion"];
export type AcceptedSuggestion = components["schemas"]["AcceptedSuggestion"];

export const calibrationKey = ["calibration"] as const;

/** The latest Rubric version's margin multiplier s and the thresholds labels suggest for it,
 * read for `version`, the version in use (none: not read), so a new one reads afresh. */
export function useCalibration(version: number | undefined) {
  return useQuery({
    queryKey: [...calibrationKey, version],
    enabled: version !== undefined,
    queryFn: async () => {
      const { data, response } = await api.GET("/api/calibration");
      if (!response.ok || !data) throw new Error(`Calibration failed: ${String(response.status)}`);
      return data;
    },
  });
}

/** Scan s on the anchor pool's labels; every Episode is then scored with it. */
export function useRunCalibration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.POST("/api/calibration/run");
      if (!response.ok || !data) throw failure(error, "Calibration failed");
      return data;
    },
    onSuccess: async (calibration) => {
      queryClient.setQueryData([...calibrationKey, calibration.rubric_version], calibration);
      // The margins every result is read with changed.
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: rubricKey }),
        queryClient.invalidateQueries({ queryKey: triageKey }),
        queryClient.invalidateQueries({ queryKey: auditKey }),
        queryClient.invalidateQueries({ queryKey: reviewKey }),
      ]);
    },
  });
}

/** Freeze the suggested threshold as the next Rubric version, and show that version. The reply
 * says whether the draft's Criterion moved too. */
export function useAcceptSuggestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (criterionId: string) => {
      const { data, error, response } = await api.POST(
        "/api/calibration/suggestions/{criterion_id}/accept",
        { params: { path: { criterion_id: criterionId } } },
      );
      if (!response.ok || !data) throw failure(error, "The suggestion couldn't be accepted");
      return data;
    },
    onSuccess: async (accepted) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: rubricKey }),
        queryClient.invalidateQueries({ queryKey: triageKey }),
        queryClient.invalidateQueries({ queryKey: calibrationKey }),
      ]);
      navigate({ version: String(accepted.version.version) });
    },
  });
}
