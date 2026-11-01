// The Describe page: write a Description on the left and compile it, then answer the interview
// under it; the live Rubric draft is on the right, edited directly on its cards, and an answer
// highlights the Criterion it changed. Every number here comes from the anchor pool (the Dev
// set), never the Test set. `?version=` shows a frozen Rubric version instead.
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

import { InfoTip } from "../core/InfoTip";
import { useSearchParams } from "../core/url";
import { InterviewTimeline } from "../interview/InterviewTimeline";
import { ConfirmAfresh } from "./ConfirmAfresh";
import { DescribeHeader } from "./DescribeHeader";
import { recompileNote } from "./recompileNote";
import { RubricPanel } from "./RubricPanel";
import { type RubricDraft, useCompile, useCompiling, useDraft } from "./useDraft";
import { useDraftEditor } from "./useDraftEditor";
import { useVersionPreview } from "./useDraftEdits";
import { useRubric, useVersions } from "./useRubric";
import { VersionPanel } from "./VersionPanel";

/** Compile, or after an edit of the draft's Description, recompile only the changed Phrases. */
function CompileRow(props: { editing: boolean; pending: boolean; empty: boolean }) {
  const { editing, pending } = props;
  return (
    <div className="mt-2 flex items-center gap-3">
      <Button type="submit" size="sm" disabled={pending || props.empty}>
        {pending ? "Compiling…" : editing ? "Recompile changes" : "Compile"}
      </Button>
      {pending && (
        <span className="text-xs text-muted-foreground">
          {editing
            ? "Spark is reading the changed Phrases against the catalog."
            : "Spark is reading it against the catalog; this can take a minute."}
        </span>
      )}
    </div>
  );
}

function RecompileNote(props: { draft: RubricDraft | null | undefined }) {
  const note = recompileNote(props.draft?.recompiled, props.draft?.phrases ?? []);
  if (!note) return null;
  return (
    <p className="mt-2 text-xs text-muted-foreground" data-testid="recompile-note">
      {note}
    </p>
  );
}

function DescriptionForm() {
  const draft = useDraft().data;
  const latest = useRubric().data;
  const compile = useCompile();
  const [edited, setEdited] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  // Starts from the draft, or else the Rubric in use.
  const text = edited ?? draft?.description ?? latest?.rubric.description ?? "";
  const editing = draft ? text.trim() !== draft.description : false;
  const run = () => {
    compile.mutate(text.trim());
  };
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        // The draft's own Description compiles afresh, losing its edits: confirm that first.
        if (draft && !editing) setConfirming(true);
        else run();
      }}
    >
      <ConfirmAfresh open={confirming} onOpenChange={setConfirming} onConfirm={run} />
      <div className="flex items-center gap-1.5">
        <label htmlFor="description" className="text-sm font-medium">
          Description
        </label>
        <InfoTip label="the Description">
          What an expert Episode looks like, in plain English. Spark compiles it into Criteria;
          after an edit, only the Phrases you changed.
        </InfoTip>
      </div>
      <Textarea
        id="description"
        className="mt-2 min-h-32 text-[15px] leading-6"
        value={text}
        onChange={(e) => {
          setEdited(e.target.value);
        }}
      />
      <CompileRow editing={editing} pending={compile.isPending} empty={!text.trim()} />
      {!compile.isPending && <RecompileNote draft={draft} />}
      {compile.error && <p className="mt-2 text-sm text-destructive">{compile.error.message}</p>}
    </form>
  );
}

/** Select the words a Phrase card asks about in the Description, to rewrite and recompile. */
function editSentence(start: number, end: number): void {
  const box = document.getElementById("description");
  if (!(box instanceof HTMLTextAreaElement)) return;
  box.focus();
  box.setSelectionRange(start, end);
}

/** The Description, and under it the interview while the draft is shown. */
function LeftColumn(props: {
  interview: boolean;
  onShowCriterion: (id: string) => void;
  onUndone: () => void;
}) {
  return (
    <div className="sticky top-32 max-h-[calc(100vh-9rem)] self-start overflow-y-auto pb-4">
      <DescriptionForm />
      {props.interview && (
        <InterviewTimeline
          onShowCriterion={props.onShowCriterion}
          onUndone={props.onUndone}
          onEditSentence={editSentence}
        />
      )}
    </div>
  );
}

/** The Criterion an interview answer changed: highlighted on its card, scrolled into view, until
 * an undo takes the change back. */
function useHighlight() {
  const [highlighted, setHighlighted] = useState<string | null>(null);
  const show = (criterionId: string) => {
    setHighlighted(criterionId);
    document
      .getElementById(`criterion-${criterionId}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  };
  const clear = () => {
    setHighlighted(null);
  };
  return { highlighted, show, clear };
}

function shownVersion(params: URLSearchParams): number | null {
  const version = Number(params.get("version"));
  return Number.isInteger(version) && version > 0 ? version : null;
}

export function DescribePage() {
  const version = shownVersion(useSearchParams());
  const draft = useDraft();
  const { editing, preview, error } = useDraftEditor(draft.data, useCompiling());
  const frozen = useVersions().data?.find((v) => v.version === version);
  const frozenPreview = useVersionPreview(version).data;
  const { highlighted, show, clear } = useHighlight();
  return (
    <div>
      <DescribeHeader
        version={version}
        draft={draft.data}
        preview={version === null ? preview : frozenPreview}
      />
      <div className="grid grid-cols-[minmax(0,5fr)_minmax(0,6fr)] gap-8 px-8 py-5">
        <LeftColumn
          interview={version === null && Boolean(draft.data)}
          onShowCriterion={show}
          onUndone={clear}
        />
        <div aria-label={version === null ? "Rubric draft" : "Rubric version"} role="region">
          {error && <p className="mb-2 text-sm text-destructive">{error.message}</p>}
          {version !== null ? (
            frozen ? (
              <VersionPanel version={frozen} preview={frozenPreview} />
            ) : (
              <p className="text-sm text-muted-foreground">Loading v{version}…</p>
            )
          ) : draft.data ? (
            <RubricPanel draft={draft.data} editing={editing} highlighted={highlighted} />
          ) : (
            <p className="text-sm text-muted-foreground">
              {draft.isPending ? "Loading…" : "Compile a Description to see its Rubric draft."}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
