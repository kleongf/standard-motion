import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import type { components } from "../../api/schema";
import { calibrationKey } from "../calibration/useCalibration";
import { reviewKey } from "../review/useReview";
import { draftKey } from "../rubric/useDraft";
import { failure } from "../rubric/useDraftEdits";
import { triageKey } from "../triage/useTriage";

export type Interview = components["schemas"]["Interview"];
export type InterviewAnswer = components["schemas"]["InterviewAnswer"];
export type PhraseQuestion = components["schemas"]["PhraseQuestion"];
export type ThresholdQuestion = components["schemas"]["ThresholdQuestion"];
export type HardSoftQuestion = components["schemas"]["HardSoftQuestion"];
export type SettingQuestion = components["schemas"]["SettingQuestion"];
export type DisagreeQuestion = components["schemas"]["DisagreeQuestion"];
export type Question =
  PhraseQuestion | ThresholdQuestion | HardSoftQuestion | SettingQuestion | DisagreeQuestion;
export type AnswerDraw = components["schemas"]["AnswerDraw"];
export type AnswerValue = AnswerDraw["answer"];

// Under the draft's key, so whatever changes the draft (compile, an edit) asks again.
const interviewKey = [...draftKey, "interview"] as const;

function isInterview(query: { queryKey: readonly unknown[] }): boolean {
  return query.queryKey[draftKey.length] === interviewKey[draftKey.length];
}

/** The interview on the Rubric draft: the answered cards and the question code asks next. */
export function useInterview() {
  return useQuery({
    queryKey: interviewKey,
    queryFn: async () => {
      const { data, response } = await api.GET("/api/interview");
      if (!response.ok || !data) throw new Error(`Interview failed: ${String(response.status)}`);
      return data;
    },
  });
}

/** An answer changes the draft and may leave a label: everything they decide reads again,
 * calibration's label count included. */
function useAfterAnswer() {
  const queryClient = useQueryClient();
  return async (interview: Interview) => {
    queryClient.setQueryData(interviewKey, interview);
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: draftKey,
        predicate: (query) => !isInterview(query),
      }),
      queryClient.invalidateQueries({ queryKey: triageKey }),
      queryClient.invalidateQueries({ queryKey: reviewKey }),
      queryClient.invalidateQueries({ queryKey: calibrationKey }),
    ]);
  };
}

export function useAnswer() {
  const after = useAfterAnswer();
  return useMutation({
    mutationFn: async (draw: AnswerDraw) => {
      const { data, error, response } = await api.POST("/api/interview/answers", { body: draw });
      if (!response.ok || !data) throw failure(error, "The answer couldn't be saved");
      return data;
    },
    onSuccess: after,
  });
}

/** Undo an answer and the later ones on the same question. */
export function useUndo() {
  const after = useAfterAnswer();
  return useMutation({
    mutationFn: async (answerId: number) => {
      const { data, error, response } = await api.DELETE("/api/interview/answers/{answer_id}", {
        params: { path: { answer_id: answerId } },
      });
      if (!response.ok || !data) throw failure(error, "The answer couldn't be undone");
      return data;
    },
    onSuccess: after,
  });
}

export type TextDraw = components["schemas"]["TextDraw"];
export type TextReply = components["schemas"]["TextReply"];

/** The curator's own words, read by Spark: to the question being asked (`question_key`), or,
 * with none, a change to the Description. Both the interview and the draft come back. */
export function useSendText() {
  const queryClient = useQueryClient();
  const after = useAfterAnswer();
  return useMutation({
    mutationFn: async (draw: TextDraw) => {
      const { data, error, response } = await api.POST("/api/interview/text", { body: draw });
      if (!response.ok || !data) throw failure(error, "Spark couldn't read that");
      return data;
    },
    onSuccess: async (reply) => {
      queryClient.setQueryData(draftKey, reply.draft);
      await after(reply.interview);
    },
  });
}
