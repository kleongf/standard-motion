// One Criterion, in the English rendered from its typed fields, with each value Spark had to
// assume marked in amber, and how it sorts the anchor pool. On the draft its card is edited
// directly, with no model call: drag the threshold, switch hard/soft, switch it on or off.
import { AlertTriangle } from "lucide-react";

import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

import { type SuggestionAction, SuggestionNote } from "../calibration/SuggestionNote";
import { AnchorHistogram } from "./AnchorHistogram";
import { ASSUMED } from "./phraseTones";
import { SanityNote } from "./SanityNote";
import type { Criterion } from "./useDraft";
import type { CriterionPreview, DraftEdit } from "./useDraftEdits";

type CriterionEdit = NonNullable<DraftEdit["criteria"]>[string];

export interface CardEditor {
  threshold: number; // shown, maybe mid-drag
  onDrag: (threshold: number) => void;
  onCommit: (threshold: number) => void;
  onEdit: (edit: CriterionEdit) => void;
}

function Toggle(props: {
  label: string;
  checked: boolean;
  onChange?: ((checked: boolean) => void) | undefined;
}) {
  return (
    <label className="flex items-center gap-1">
      <Switch
        size="sm"
        aria-label={props.label}
        checked={props.checked}
        disabled={!props.onChange}
        onCheckedChange={props.onChange}
      />
      {props.label}
    </label>
  );
}

function AnchorCounts(props: { preview: CriterionPreview }) {
  const { passing, failing, unsure } = props.preview;
  return (
    <p className="mt-1 text-xs text-muted-foreground tabular-nums" data-testid="anchor-counts">
      Anchor pool: <span className="text-emerald-700 dark:text-emerald-400">{passing} pass</span>
      {" · "}
      <span className="text-rose-700 dark:text-rose-400">{failing} fail</span>
      {" · "}
      <span className="text-amber-700 dark:text-amber-400">{unsure} unsure</span>
    </p>
  );
}

function CardHeader(props: {
  criterion: Criterion;
  enabled: boolean;
  editor?: CardEditor | undefined;
}) {
  const { criterion, enabled, editor } = props;
  const state = !enabled ? "off · not scored" : criterion.hard ? "" : "soft · never rejects";
  return (
    <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
      <code className="font-semibold text-foreground">{criterion.primitive}</code>
      <span className="rounded border px-1">{criterion.kind}</span>
      <span className="ml-auto">{state}</span>
      <Toggle
        label="Hard"
        checked={criterion.hard}
        onChange={
          editor &&
          ((hard) => {
            editor.onEdit({ hard });
          })
        }
      />
      <Toggle
        label="On"
        checked={enabled}
        onChange={
          editor &&
          ((on) => {
            editor.onEdit({ enabled: on });
          })
        }
      />
    </div>
  );
}

function AnchorSortOf(props: {
  criterion: Criterion;
  label: string;
  preview: CriterionPreview;
  editor?: CardEditor | undefined;
  suggested?: number | undefined;
}) {
  const { preview, editor } = props;
  return (
    <>
      <AnchorHistogram
        preview={preview}
        threshold={editor?.threshold ?? preview.threshold}
        anchor={props.criterion.threshold}
        label={props.label}
        suggested={props.suggested}
        onDrag={editor?.onDrag}
        onCommit={editor?.onCommit}
      />
      <AnchorCounts preview={preview} />
      <SanityNote preview={preview} />
    </>
  );
}

export function CriterionCard(props: {
  criterion: Criterion;
  english: string;
  enabled: boolean;
  preview?: CriterionPreview | undefined;
  editor?: CardEditor | undefined; // none on a frozen Rubric version
  highlighted?: boolean; // an interview answer just changed it
  suggestion?: SuggestionAction | undefined; // a threshold labels suggest, on the version in use
}) {
  const { criterion, preview } = props;
  return (
    <article
      id={`criterion-${criterion.id}`}
      aria-label={props.english}
      data-highlighted={props.highlighted ? "true" : undefined}
      className={cn(
        "rounded-lg border bg-card p-3 transition-shadow",
        !props.enabled && "opacity-60",
        props.highlighted && "ring-2 ring-sky-400 dark:ring-sky-600",
      )}
    >
      <CardHeader criterion={criterion} enabled={props.enabled} editor={props.editor} />
      {/* The preview carries any threshold mid-drag, so its English is the one to read. */}
      <p className="mt-1 text-sm" data-testid="criterion-english">
        {preview?.english ?? props.english}
      </p>
      {preview && (
        <AnchorSortOf
          criterion={criterion}
          label={`Threshold: ${props.english}`}
          preview={preview}
          editor={props.editor}
          suggested={props.suggestion?.suggestion.suggested_threshold}
        />
      )}
      {props.suggestion && <SuggestionNote action={props.suggestion} />}
      {criterion.assumptions.map((assumption) => (
        <p
          key={assumption}
          className={`mt-2 flex items-start gap-1.5 px-2 py-1 text-xs ${ASSUMED}`}
          data-testid="assumption"
        >
          <AlertTriangle className="mt-0.5 size-3 shrink-0" />
          <span>Assumed: {assumption}</span>
        </p>
      ))}
    </article>
  );
}
