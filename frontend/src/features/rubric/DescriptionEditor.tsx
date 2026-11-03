// The composer holding the Description: sending it compiles it, and once there is a draft,
// sending an edit of it recompiles only the changed Phrases. Sending the draft's own Description
// again compiles afresh, losing its edits, so that asks first. Opened on a Phrase question's
// sentence, it selects those words to rewrite.
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

import { ComposerBox } from "./ComposerBox";
import { ConfirmAfresh } from "./ConfirmAfresh";
import { useCompile, useDraft } from "./useDraft";
import { useRubric } from "./useRubric";

export interface Selection {
  start: number;
  end: number;
}

function sendLabel(pending: boolean, editing: boolean): string {
  if (pending) return "Compiling…";
  return editing ? "Recompile changes" : "Compile";
}

/** Focus the box once it opens, with `selection` selected or else the caret at the end. */
function useFocusOnOpen(open: boolean, selection: Selection | null) {
  const box = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = box.current;
    if (!open || !el) return;
    el.focus();
    const end = el.value.length;
    el.setSelectionRange(selection?.start ?? end, selection?.end ?? end);
  }, [open, selection]);
  return box;
}

function CancelEditing(props: { onCancel?: (() => void) | undefined }) {
  if (!props.onCancel) return null;
  return (
    <div className="mt-1.5 flex items-center px-1">
      <Button type="button" size="xs" variant="ghost" className="ml-auto" onClick={props.onCancel}>
        Cancel editing
      </Button>
    </div>
  );
}

export function DescriptionEditor(props: {
  onSent: () => void;
  /** Set once there is a draft: back to talking with Spark. */
  onCancel?: () => void;
  selection?: Selection | null;
}) {
  const draft = useDraft().data;
  const latest = useRubric().data;
  const compile = useCompile();
  const [edited, setEdited] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const box = useFocusOnOpen(Boolean(props.onCancel), props.selection ?? null);
  // Starts from the draft, or else the Rubric in use.
  const text = edited ?? draft?.description ?? latest?.rubric.description ?? "";
  const editing = draft ? text.trim() !== draft.description : false;
  const run = () => {
    compile.mutate(text.trim(), { onSuccess: props.onSent });
  };
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!text.trim() || compile.isPending) return;
        // The draft's own Description compiles afresh, losing its edits: confirm that first.
        if (draft && !editing) setConfirming(true);
        else run();
      }}
    >
      <ConfirmAfresh open={confirming} onOpenChange={setConfirming} onConfirm={run} />
      {compile.error && <p className="mb-2 text-sm text-destructive">{compile.error.message}</p>}
      <ComposerBox
        id="description"
        label="Description"
        value={text}
        placeholder="Describe what an expert Episode looks like…"
        sendLabel={sendLabel(compile.isPending, editing)}
        pending={compile.isPending}
        canSend={Boolean(text.trim())}
        onChange={setEdited}
        onSend={() => {
          box.current?.form?.requestSubmit();
        }}
        ref={box}
      />
      <CancelEditing onCancel={props.onCancel} />
    </form>
  );
}
