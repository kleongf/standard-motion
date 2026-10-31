// The composer at the foot of the Describe conversation. It holds the Description: sending it
// compiles it, and once there is a draft, sending an edit of it recompiles only the changed
// Phrases. Sending the draft's own Description again compiles afresh, losing its edits, so that
// asks first. Enter sends; Shift+Enter starts a new line.
import { ArrowUp, Loader2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

import { InfoTip } from "../core/InfoTip";
import { ConfirmAfresh } from "./ConfirmAfresh";
import { useCompile, useDraft } from "./useDraft";
import { useRubric } from "./useRubric";

export const COMPOSER_ID = "description";

/** Select the words a Phrase question asks about in the composer, to rewrite and send. */
export function editSentence(start: number, end: number): void {
  const box = document.getElementById(COMPOSER_ID);
  if (!(box instanceof HTMLTextAreaElement)) return;
  box.focus();
  box.setSelectionRange(start, end);
}

function sendLabel(pending: boolean, editing: boolean): string {
  if (pending) return "Compiling…";
  return editing ? "Recompile changes" : "Compile";
}

function ComposerHint(props: { drafted: boolean }) {
  return (
    <div className="mt-1.5 flex items-center gap-1.5 px-1 text-xs text-muted-foreground">
      <span>
        {props.drafted
          ? "Edit the Description and send it: only the Phrases you change recompile."
          : "Spark compiles it into Criteria that code checks on every Episode."}
      </span>
      <InfoTip label="the Description">
        What an expert Episode looks like, in plain English. Spark compiles it into Criteria; after
        an edit, only the Phrases you changed.
      </InfoTip>
    </div>
  );
}

export function DescribeComposer(props: { onSent: () => void }) {
  const draft = useDraft().data;
  const latest = useRubric().data;
  const compile = useCompile();
  const [edited, setEdited] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  // Starts from the draft, or else the Rubric in use.
  const text = edited ?? draft?.description ?? latest?.rubric.description ?? "";
  const editing = draft ? text.trim() !== draft.description : false;
  const empty = !text.trim();
  const run = () => {
    compile.mutate(text.trim(), { onSuccess: props.onSent });
  };
  const send = () => {
    if (empty || compile.isPending) return;
    // The draft's own Description compiles afresh, losing its edits: confirm that first.
    if (draft && !editing) setConfirming(true);
    else run();
  };
  const label = sendLabel(compile.isPending, editing);
  return (
    <div className="sticky bottom-0 z-10 bg-gradient-to-t from-background from-75% to-transparent pt-6 pb-5">
      <form
        className="mx-auto max-w-3xl px-6"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <ConfirmAfresh open={confirming} onOpenChange={setConfirming} onConfirm={run} />
        {compile.error && <p className="mb-2 text-sm text-destructive">{compile.error.message}</p>}
        <div className="relative rounded-2xl border bg-card shadow-sm focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/30">
          <Textarea
            id={COMPOSER_ID}
            aria-label="Description"
            value={text}
            onChange={(e) => {
              setEdited(e.target.value);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            rows={1}
            placeholder="Describe what an expert Episode looks like…"
            className="max-h-48 min-h-14 resize-none border-0 bg-transparent px-4 py-3.5 pr-14 text-[15px] shadow-none focus-visible:ring-0 md:text-[15px] dark:bg-transparent"
          />
          <Button
            type="submit"
            size="icon"
            aria-label={label}
            title={label}
            disabled={empty || compile.isPending}
            className="absolute right-2.5 bottom-2.5 rounded-full"
          >
            {compile.isPending ? <Loader2 className="animate-spin" /> : <ArrowUp />}
          </Button>
        </div>
        <ComposerHint drafted={Boolean(draft)} />
      </form>
    </div>
  );
}
