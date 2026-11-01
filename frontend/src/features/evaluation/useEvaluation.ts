import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import type { components } from "../../api/schema";

export type EvaluationReport = components["schemas"]["EvaluationReport"];
export type EvaluationRequest = components["schemas"]["EvaluationRequest"];
export type SystemRow = components["schemas"]["SystemRow"];
export type Proportion = components["schemas"]["Proportion"];
export type LengthRule = components["schemas"]["LengthRule"];
export type TestRun = components["schemas"]["TestRun"];
export type Slack = components["schemas"]["Slack"];
export type RightReasonRow = components["schemas"]["RightReasonRow"];
export type RiskCoverage = components["schemas"]["RiskCoverage"];
export type MatchedCoverage = components["schemas"]["MatchedCoverage"];
export type McNemar = components["schemas"]["McNemar"];
export type PhraseFailures = components["schemas"]["PhraseFailures"];
export type AblationRow = components["schemas"]["AblationRow"];
export type TrackHealthRow = components["schemas"]["TrackHealthRow"];
export type MetaCost = components["schemas"]["MetaCost"];
export type ReviewTime = components["schemas"]["ReviewTime"];
export type DatasetOutcome = components["schemas"]["DatasetOutcome"];
export type FailBenchCheck = components["schemas"]["FailBenchCheck"];
export type Disagreement = components["schemas"]["Disagreement"];

const testRunsKey = ["evaluation", "test-runs"] as const;

/** Every logged Test set run, newest first. */
export function useTestRuns() {
  return useQuery({
    queryKey: testRunsKey,
    queryFn: async () => {
      const { data, response } = await api.GET("/api/evaluation/test-runs");
      if (!response.ok || !data) throw new Error(`Test runs failed: ${String(response.status)}`);
      return data;
    },
  });
}

/** Episodes where Spark alone and Winnow disagree, scored live on every read. */
export function useDisagreements() {
  return useQuery({
    queryKey: ["evaluation", "disagreements"],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/evaluation/disagreements");
      if (!response.ok || !data)
        throw new Error(`Disagreements failed: ${String(response.status)}`);
      return data;
    },
  });
}

/** Score Winnow and the baselines on a set; a Test set run is also logged. */
export function useRunEvaluation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (request: EvaluationRequest) => {
      const { data, error, response } = await api.POST("/api/evaluation/runs", {
        body: request,
      });
      if (!response.ok || !data) {
        const detail = (error as { detail?: unknown } | undefined)?.detail;
        throw new Error(typeof detail === "string" ? detail : "The evaluation couldn't run");
      }
      return data;
    },
    onSuccess: async (report) => {
      if (report.set_name === "test") {
        await queryClient.invalidateQueries({ queryKey: testRunsKey });
      }
    },
  });
}
