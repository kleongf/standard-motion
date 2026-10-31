// The Describe page, as a conversation with Spark: the curator sends a Description, Spark compiles
// it into the Rubric draft (a card in the conversation, edited directly on its Criterion cards),
// then asks about what it assumed, one anchored question at a time. Editing the Description in
// the composer recompiles only the changed Phrases; Run in the top bar freezes the draft. Every
// number here comes from the anchor pool (the Dev set), never the Test set. `?version=` shows a
// frozen Rubric version instead.
import { useEffect, useRef, useState } from "react";

import { useSearchParams } from "../core/url";
import { useInterview } from "../interview/useInterview";
import { DescribeComposer } from "./DescribeComposer";
import { DescribeHeader } from "./DescribeHeader";
import { DescribeThread } from "./DescribeThread";
import { useCompiling, useDraft } from "./useDraft";
import { useDraftEditor } from "./useDraftEditor";
import { useRun, useVersionPreview } from "./useDraftEdits";
import { useVersions } from "./useRubric";
import { VersionPanel } from "./VersionPanel";

/** The Criterion an interview answer changed: highlighted on its card until an undo takes the
 * change back. Clicking an answer scrolls up to it. */
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
  return { highlighted, mark: setHighlighted, show, clear };
}

/** After the next render, scroll to the newest turn. */
function scrollToEnd(behavior: ScrollBehavior = "smooth"): void {
  requestAnimationFrame(() => {
    window.scrollTo({ top: document.documentElement.scrollHeight, behavior });
  });
}

/** Open a conversation where it left off: at its end, once what it shows is in. */
function useResumeAtEnd(ready: boolean): void {
  const resumed = useRef(false);
  useEffect(() => {
    if (!ready || resumed.current) return;
    resumed.current = true;
    scrollToEnd("auto");
  }, [ready]);
}

function shownVersion(params: URLSearchParams): number | null {
  const version = Number(params.get("version"));
  return Number.isInteger(version) && version > 0 ? version : null;
}

function FrozenVersion(props: { version: number }) {
  const { version } = props;
  const frozen = useVersions().data?.find((v) => v.version === version);
  const preview = useVersionPreview(version).data;
  return (
    <div>
      <DescribeHeader version={version} preview={preview} />
      <div aria-label="Rubric version" role="region" className="mx-auto max-w-3xl px-6 py-6">
        {frozen ? (
          <VersionPanel version={frozen} preview={preview} />
        ) : (
          <p className="text-sm text-muted-foreground">Loading v{version}…</p>
        )}
      </div>
    </div>
  );
}

function Conversation() {
  const draft = useDraft();
  const compiling = useCompiling();
  const interview = useInterview();
  const { editing, preview, error } = useDraftEditor(draft.data, compiling);
  const run = useRun();
  const { highlighted, mark, show, clear } = useHighlight();
  // The previews size the Rubric card's histograms: wait for them too, or the end moves.
  useResumeAtEnd(
    draft.isSuccess && (draft.data === null || (interview.isSuccess && preview !== undefined)),
  );
  return (
    <div className="flex min-h-screen flex-col">
      <DescribeHeader
        version={null}
        draft={draft.data}
        preview={preview}
        run={{
          pending: run.isPending,
          onRun: () => {
            run.mutate(undefined, {
              onSuccess: () => {
                scrollToEnd();
              },
            });
          },
        }}
      />
      {run.error && <p className="px-8 pt-3 text-sm text-destructive">{run.error.message}</p>}
      <DescribeThread
        draft={draft.data}
        compiling={compiling}
        editing={editing}
        error={error}
        highlighted={highlighted}
        ran={run.data?.version ?? null}
        onChanged={mark}
        onShowCriterion={show}
        onUndone={clear}
        onAnswered={() => {
          scrollToEnd();
        }}
      />
      <DescribeComposer
        onSent={() => {
          scrollToEnd();
        }}
      />
    </div>
  );
}

export function DescribePage() {
  const version = shownVersion(useSearchParams());
  return version === null ? <Conversation /> : <FrozenVersion version={version} />;
}
