// The Describe conversation, rebuilt from the server's state each time, so a reload resumes it:
// Spark's greeting; the curator's Description, each Phrase tinted and linked to its section; what
// the compile made of it; the Rubric draft as a card that updates in place; the interview; and
// what Run froze, once it has run here.
import { InterviewThread } from "../interview/InterviewThread";
import { editSentence } from "./DescribeComposer";
import { AnchorPoolLine } from "./DescribeHeader";
import { DescriptionText } from "./DescriptionText";
import { recompileNote } from "./recompileNote";
import { RubricCard } from "./RubricCard";
import type { DraftEditing } from "./RubricPanel";
import { RunCard } from "./RunCard";
import { AgentRow, TypingIndicator, UserBubble } from "./ThreadParts";
import type { RubricDraft } from "./useDraft";

function plural(n: number, one: string, many: string): string {
  return `${String(n)} ${n === 1 ? one : many}`;
}

function Greeting() {
  return (
    <AgentRow>
      <p>
        Describe what an expert Episode looks like, in your own words. I’ll compile it into Criteria
        that code checks on every Episode, then check anything I had to assume against a real
        moment.
      </p>
      <div className="mt-1">
        <AnchorPoolLine />
      </div>
    </AgentRow>
  );
}

function CompileSummary(props: { draft: RubricDraft; compiling: boolean }) {
  const { draft } = props;
  const note = props.compiling ? null : recompileNote(draft.recompiled, draft.phrases);
  const assumed = draft.assumptions_unconfirmed;
  return (
    <AgentRow>
      <p>
        {note ? (
          <span data-testid="recompile-note">{note}</span>
        ) : (
          `I split it into ${plural(draft.phrases.length, "Phrase", "Phrases")} and compiled ${plural(draft.criteria.length, "Criterion", "Criteria")}.`
        )}{" "}
        {assumed > 0 &&
          `I assumed ${plural(assumed, "value", "values")} the Description doesn’t state; I’ll check them with you below.`}
      </p>
      {draft.uncovered.length > 0 && (
        <p className="mt-1 text-sm text-muted-foreground">
          Wavy underlines mark words in no Phrase: nothing checks them.
        </p>
      )}
      {draft.rejected.map((r) => (
        <p key={r.text} className="mt-1 text-sm text-destructive" data-testid="rejected-phrase">
          I proposed “{r.text}”, refused: {r.reason}
        </p>
      ))}
    </AgentRow>
  );
}

export function DescribeThread(props: {
  draft: RubricDraft | null | undefined;
  compiling: boolean;
  editing: DraftEditing;
  error: Error | null;
  highlighted: string | null;
  ran: number | null;
  onChanged: (criterionId: string) => void;
  onShowCriterion: (criterionId: string) => void;
  onUndone: () => void;
  onAnswered: () => void;
}) {
  const { draft } = props;
  return (
    <div className="mx-auto grid w-full max-w-3xl flex-1 content-start gap-6 px-6 pt-8 pb-4">
      <Greeting />
      {draft && (
        <>
          <UserBubble>
            <DescriptionText draft={draft} />
          </UserBubble>
          <CompileSummary draft={draft} compiling={props.compiling} />
          <AgentRow mark={false}>
            <RubricCard
              draft={draft}
              editing={props.editing}
              highlighted={props.highlighted}
              error={props.error}
            />
          </AgentRow>
          <InterviewThread
            onChanged={props.onChanged}
            onShowCriterion={props.onShowCriterion}
            onUndone={props.onUndone}
            onEditSentence={editSentence}
            onAnswered={props.onAnswered}
          />
        </>
      )}
      {props.compiling && (
        <TypingIndicator label="Spark is reading it against the catalog; this can take a minute." />
      )}
      {props.ran !== null && (
        <AgentRow>
          <RunCard version={props.ran} />
        </AgentRow>
      )}
    </div>
  );
}
