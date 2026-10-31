// An answered question in the conversation, collapsed to the answer and its effect. Clicking it
// shows the Criterion it changed on the Rubric card; Undo takes it back, with the later answers on
// the same question.
import { CheckCircle2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import type { AnswerValue, InterviewAnswer } from "./useInterview";

const ANSWER_LABELS: Record<AnswerValue, string> = {
  accept: "left unchecked",
  context: "marked Context",
  pass: "fine",
  fail: "not fine",
  hard: "hard",
  soft: "soft",
  skip: "skipped",
};

/** What a grasp-setting answer said of the moment it was asked about. */
function settingSaid(key: string, value: AnswerValue): string {
  const rise = key === "setting:grasp_rise_m";
  if (value === "pass") return rise ? "lifted" : "closed";
  if (value === "fail") return rise ? "not lifted" : "open";
  return ANSWER_LABELS[value];
}

/** What a disagree answer said the Phrase did on its Episode. */
const PHRASE_SAID: Partial<Record<AnswerValue, string>> = { pass: "passes", fail: "fails" };

function heading(answer: InterviewAnswer): string {
  const phraseSaid = PHRASE_SAID[answer.answer];
  if (answer.kind === "disagree" && answer.episode_id && phraseSaid) {
    return `“${answer.subject}” on ${answer.episode_id}: ${phraseSaid}`;
  }
  if (answer.kind === "setting" && answer.measurement && answer.episode_id) {
    const said = settingSaid(answer.key, answer.answer);
    return `${answer.subject}: ${answer.measurement} on ${answer.episode_id}, ${said}`;
  }
  if (answer.measurement && answer.episode_id) {
    return `${answer.measurement} on ${answer.episode_id}: ${ANSWER_LABELS[answer.answer]}`;
  }
  return `“${answer.subject}”: ${ANSWER_LABELS[answer.answer]}`;
}

export function AnsweredCard(props: {
  answer: InterviewAnswer;
  pending: boolean;
  onUndo: (answerId: number) => void;
  onShow: (criterionId: string) => void;
}) {
  const { answer, pending, onUndo, onShow } = props;
  const changed = answer.changed_criterion;
  return (
    <article
      aria-label={`Answer: ${answer.subject}`}
      className={cn(
        "rounded-lg border bg-card/60 px-3 py-2 text-sm",
        changed && "cursor-pointer hover:bg-muted/60",
      )}
      onClick={() => {
        if (changed) onShow(changed);
      }}
    >
      <div className="flex items-start gap-2">
        <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
        <p className="min-w-0 flex-1 font-medium">{heading(answer)}</p>
        <Button
          size="xs"
          variant="ghost"
          disabled={pending}
          onClick={(event) => {
            event.stopPropagation();
            onUndo(answer.id);
          }}
        >
          Undo
        </Button>
      </div>
      <p className="mt-0.5 pl-6 text-xs text-muted-foreground" data-testid="answer-effect">
        {answer.effect}
      </p>
    </article>
  );
}
