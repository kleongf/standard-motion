// The Describe page's top bar: how the shown Rubric sorts the anchor pool, the draft's dry run
// while Spark asks its visual Criteria, a chip that jumps to the Rubric card, the Rubric version
// select, and Run, which never blocks.
import { FileText } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { navigate } from "../core/url";
import { DryRunProgress } from "./DryRunProgress";
import { scrollToRubric } from "./RubricCard";
import { warningCount } from "./sanity";
import { type RubricDraft, useAnchorPool } from "./useDraft";
import type { AnchorPreview } from "./useDraftEdits";
import { useDryRun } from "./useDryRun";
import { useVersions } from "./useRubric";

function plural(n: number, word: string): string {
  return `${String(n)} ${word}${n === 1 ? "" : "s"}`;
}

/** The Episodes every number comes from: the Dev set, never the Test set. */
export function AnchorPoolLine() {
  const pool = useAnchorPool().data;
  if (!pool) return null;
  return (
    <p className="text-xs text-muted-foreground" data-testid="anchor-pool">
      Anchor pool: <span className="font-medium text-foreground">Dev set</span> ·{" "}
      {plural(pool.episode_ids.length, "Episode")} ·{" "}
      {plural(pool.hidden_test_episodes, "Test set Episode")} hidden
      {pool.awaiting_reference_label > 0 &&
        ` · ${String(pool.awaiting_reference_label)} awaiting a Reference label, so not counted`}
    </p>
  );
}

function AnchorSort(props: { preview?: AnchorPreview | undefined }) {
  if (!props.preview) return null;
  const { keep, reject, needs_review: review } = props.preview;
  return (
    <p className="text-xs text-muted-foreground tabular-nums" data-testid="anchor-sort">
      Sorts it: <span className="text-emerald-700 dark:text-emerald-400">{keep} Keep</span> ·{" "}
      <span className="text-rose-700 dark:text-rose-400">{reject} Reject</span> ·{" "}
      <span className="text-amber-700 dark:text-amber-400">{review} Needs review</span>
    </p>
  );
}

function SanityCount(props: { preview?: AnchorPreview | undefined }) {
  const warnings = warningCount(props.preview);
  if (warnings === 0) return null;
  return (
    <p className="text-xs text-amber-700 dark:text-amber-400" data-testid="sanity-count">
      · {plural(warnings, "Rubric warning")}
    </p>
  );
}

/** Its answers refresh the draft's preview as they come in. */
function DraftDryRun(props: { draft: RubricDraft | null | undefined }) {
  return <DryRunProgress job={useDryRun(props.draft)} />;
}

function VersionSelect(props: { version: number | null }) {
  const versions = useVersions().data ?? [];
  return (
    <Select
      value={props.version === null ? "draft" : String(props.version)}
      onValueChange={(value) => {
        navigate({ version: value === "draft" ? null : value });
      }}
    >
      <SelectTrigger size="sm" aria-label="Rubric version" className="w-44">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="draft">Draft</SelectItem>
        {versions.map((v, i) => (
          <SelectItem key={v.version} value={String(v.version)}>
            v{v.version} · {v.origin === "seed" ? "seeded" : "run"}
            {i === 0 ? " · in use" : ""}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function runLabel(next: number, unconfirmed: number): string {
  const assumptions = unconfirmed > 0 ? ` · ${plural(unconfirmed, "assumption")} unconfirmed` : "";
  return `Run v${String(next)}${assumptions}`;
}

interface Run {
  pending: boolean;
  onRun: () => void;
}

function RunButton(props: { draft?: RubricDraft | null | undefined; run: Run }) {
  const { run } = props;
  const next = (useVersions().data?.[0]?.version ?? 0) + 1;
  const label = runLabel(next, props.draft?.assumptions_unconfirmed ?? 0);
  return (
    <Button size="sm" disabled={!props.draft || run.pending} onClick={run.onRun}>
      {run.pending ? "Running…" : label}
    </Button>
  );
}

function RubricChip() {
  return (
    <button
      type="button"
      onClick={scrollToRubric}
      className="inline-flex h-8 items-center gap-1.5 rounded-full border bg-card px-3 text-xs font-medium hover:bg-muted"
    >
      <FileText className="size-3.5 text-muted-foreground" />
      Rubric
    </button>
  );
}

export function DescribeHeader(props: {
  version: number | null;
  draft?: RubricDraft | null | undefined;
  preview?: AnchorPreview | undefined;
  run?: Run;
}) {
  const drafting = props.version === null;
  return (
    <header className="sticky top-0 z-20 border-b bg-background/85 backdrop-blur">
      <div className="flex h-14 items-center gap-3 px-8">
        <div className="min-w-0 flex-1">
          {/* The dry run sits beside the title: the line under it is full with the sort. */}
          <div className="flex items-center gap-3 truncate">
            <h1 className="text-base leading-tight font-semibold">Describe &amp; run</h1>
            {drafting && <DraftDryRun draft={props.draft} />}
          </div>
          <div className="flex gap-1 truncate">
            <AnchorSort preview={props.preview} />
            <SanityCount preview={props.preview} />
          </div>
        </div>
        {drafting && props.draft && <RubricChip />}
        <VersionSelect version={props.version} />
        {drafting && props.run && <RunButton draft={props.draft} run={props.run} />}
      </div>
    </header>
  );
}
