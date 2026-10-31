// The question code is asking now, worded from a template, as Spark's turn in the conversation. A
// Phrase card asks what to do with an Unsupported Phrase or words in no Phrase; a threshold card
// plays one anchor Episode's measured stretch and asks whether its value is fine, one step of
// bisecting an assumed threshold; a hard/soft card asks whether failing a Criterion rejects an
// Episode; a setting card asks whether the gripper is closed (or lifted) at one anchor Episode's
// moment, one step of bisecting a grasp setting; a disagree card asks whether a Phrase passes on
// an anchor Episode its Criteria disagree on.
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { Pill } from "../triage/Pill";
import { AnchorClip } from "./AnchorClip";
import { DisagreeDetails } from "./DisagreeDetails";
import type { AnswerValue, Question, SettingQuestion, ThresholdQuestion } from "./useInterview";

const KIND_LABELS: Record<Question["kind"], string> = {
  phrase: "Unsupported Phrase",
  words: "In no Phrase",
  threshold: "Assumed threshold",
  hard_soft: "Hard or soft",
  setting: "Assumed grasp setting",
  disagree: "Criteria disagree",
};

function Step(props: { episodeId: string; asked: number; max: number; children?: string }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Pill tone="neutral" className="font-mono">
        {props.episodeId}
      </Pill>
      {props.children && <Pill tone="unsure">{props.children}</Pill>}
      <span className="text-xs text-muted-foreground">
        Question {props.asked + 1} of at most {props.max}
      </span>
    </div>
  );
}

function ThresholdDetails(props: { question: ThresholdQuestion }) {
  const { question } = props;
  return (
    <>
      <AnchorClip question={question} />
      <Step episodeId={question.episode_id} asked={question.asked} max={question.max_questions}>
        {question.measurement}
      </Step>
      {question.near > 0 && (
        <p className="-mt-1 text-xs text-muted-foreground">
          {question.near} anchor Episodes sit near it
        </p>
      )}
    </>
  );
}

function SettingDetails(props: { question: SettingQuestion }) {
  const { question } = props;
  return (
    <>
      <AnchorClip question={question} />
      <Step episodeId={question.episode_id} asked={question.asked} max={question.max_questions} />
    </>
  );
}

/** What the question checks today, under its prompt. */
function today(question: Question): string | null {
  if (question.kind === "threshold") return `Today: ${question.english}`;
  if (question.kind === "setting") return `${question.name} · ${question.assumption}`;
  return null;
}

export function QuestionCard(props: {
  question: Question;
  pending: boolean;
  onAnswer: (answer: AnswerValue) => void;
  onEditSentence?: (start: number, end: number) => void;
}) {
  const { question, pending, onAnswer, onEditSentence } = props;
  const now = today(question);
  return (
    <section aria-label="Question" className="grid gap-3">
      <p className="text-[11px] font-semibold tracking-wide text-primary uppercase">
        {KIND_LABELS[question.kind]}
      </p>
      {question.kind === "threshold" && <ThresholdDetails question={question} />}
      {question.kind === "setting" && <SettingDetails question={question} />}
      {question.kind === "disagree" && <DisagreeDetails question={question} />}
      <p className="text-lg leading-snug font-medium text-balance">{question.prompt}</p>
      {now && <p className="text-xs text-muted-foreground">{now}</p>}
      <div className="grid gap-2 sm:grid-cols-2">
        {question.options.map((option) => (
          <button
            key={option.answer}
            type="button"
            disabled={pending}
            onClick={() => {
              onAnswer(option.answer);
            }}
            className={cn(
              "rounded-xl border bg-card px-4 py-3 text-left text-sm font-medium shadow-xs transition-colors hover:border-primary/50 hover:bg-primary/5 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none disabled:opacity-50",
              option.answer === "skip" && "border-dashed font-normal text-muted-foreground",
            )}
          >
            {option.label}
          </button>
        ))}
      </div>
      {(question.kind === "phrase" || question.kind === "words") && onEditSentence && (
        <div>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              onEditSentence(question.start, question.end);
            }}
          >
            Edit the sentence
          </Button>
        </div>
      )}
    </section>
  );
}
