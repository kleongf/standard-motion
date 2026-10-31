// The interview as turns of the Describe conversation, after the Rubric card: each answered
// question collapsed to its effect, then where the interview stands and the one question code asks
// next. It is done once every Phrase is covered; assumed thresholds, hard or soft, assumed grasp
// settings and Phrases whose Criteria disagree can still be asked after that, and Run never waits
// for them.
import { AgentRow } from "../rubric/ThreadParts";
import { AnsweredCard } from "./AnsweredCard";
import { QuestionCard } from "./QuestionCard";
import { type Interview, useAnswer, useInterview, useUndo } from "./useInterview";

function plural(n: number, word: string): string {
  return `${String(n)} ${word}${n === 1 ? "" : "s"}`;
}

function stillAsked(interview: Interview): string {
  const left = [
    [interview.thresholds_left, "assumed threshold"],
    [interview.hard_soft_left, "hard-or-soft question"],
    [interview.settings_left, "assumed grasp setting"],
    [interview.disagree_left, "Criteria-disagree question"],
  ] as const;
  const counts = left.filter(([n]) => n > 0).map(([n, word]) => plural(n, word));
  return counts.length > 0 ? ` Can still be asked: ${counts.join(", ")}.` : "";
}

function Status(props: { interview: Interview }) {
  const { covered, phrases_left: phrases } = props.interview;
  const left = stillAsked(props.interview);
  return (
    <p data-testid="interview-status">
      {covered
        ? `Every Phrase is covered: the interview is done.${left}`
        : `${plural(phrases, "Phrase")} to cover before the interview is done.`}
    </p>
  );
}

export function InterviewThread(props: {
  /** An answer changed this Criterion: mark it on the Rubric card. */
  onChanged: (criterionId: string) => void;
  /** Scroll to this Criterion on the Rubric card. */
  onShowCriterion: (criterionId: string) => void;
  onUndone: () => void;
  onEditSentence: (start: number, end: number) => void;
  onAnswered: () => void;
}) {
  const interview = useInterview();
  const answer = useAnswer();
  const undo = useUndo();
  const pending = answer.isPending || undo.isPending;
  const data = interview.data;
  if (!data) return null;
  const error = answer.error ?? undo.error;
  const question = data.question;
  return (
    <section aria-label="Interview" className="grid gap-6">
      {data.answered.length > 0 && (
        <AgentRow mark={false}>
          <ol aria-label="Answers" className="grid gap-1.5">
            {data.answered.map((a) => (
              <li key={a.id}>
                <AnsweredCard
                  answer={a}
                  pending={pending}
                  onShow={props.onShowCriterion}
                  onUndo={(id) => {
                    undo.mutate(id, { onSuccess: props.onUndone });
                  }}
                />
              </li>
            ))}
          </ol>
        </AgentRow>
      )}
      <AgentRow>
        <div className="grid gap-4">
          <Status interview={data} />
          {error && <p className="text-sm text-destructive">{error.message}</p>}
          {question && (
            <QuestionCard
              key={`${question.key}:${String(data.answered.length)}`}
              question={question}
              pending={pending}
              onEditSentence={props.onEditSentence}
              onAnswer={(value) => {
                const episodeId = "episode_id" in question ? question.episode_id : null;
                answer.mutate(
                  { key: question.key, episode_id: episodeId, answer: value },
                  {
                    onSuccess: (next) => {
                      const changed = next.answered.at(-1)?.changed_criterion;
                      if (changed) props.onChanged(changed);
                      props.onAnswered();
                    },
                  },
                );
              }}
            />
          )}
        </div>
      </AgentRow>
    </section>
  );
}
