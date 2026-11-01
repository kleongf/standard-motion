// The Describe page's header: the anchor pool every number comes from, how the shown Rubric
// sorts it, the Rubric version select, and Run, which never blocks.
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { navigate } from "../core/url";
import { type RubricDraft, useAnchorPool } from "./useDraft";
import { warningCount } from "./sanity";
import { type AnchorPreview, useRun } from "./useDraftEdits";
import { useVersions } from "./useRubric";

function plural(n: number, word: string): string {
  return `${String(n)} ${word}${n === 1 ? "" : "s"}`;
}

function AnchorPoolLine() {
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
      {plural(warnings, "Rubric warning")}: see the Criteria marked below
    </p>
  );
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

function RunButton(props: { draft?: RubricDraft | null | undefined }) {
  const run = useRun();
  const next = (useVersions().data?.[0]?.version ?? 0) + 1;
  const label = runLabel(next, props.draft?.assumptions_unconfirmed ?? 0);
  return (
    <div className="flex items-center gap-2">
      {run.data && (
        <span className="text-xs text-muted-foreground" data-testid="run-result">
          v{run.data.version} frozen; every Episode is scored against it
        </span>
      )}
      {run.error && <span className="text-xs text-destructive">{run.error.message}</span>}
      <Button
        size="sm"
        disabled={!props.draft || run.isPending}
        onClick={() => {
          run.mutate();
        }}
      >
        {run.isPending ? "Running…" : label}
      </Button>
    </div>
  );
}

export function DescribeHeader(props: {
  version: number | null;
  draft?: RubricDraft | null | undefined;
  preview?: AnchorPreview | undefined;
}) {
  return (
    <header className="sticky top-0 z-10 flex items-end gap-4 border-b bg-background/95 px-8 py-3 backdrop-blur">
      <div className="min-w-0 flex-1">
        <h1 className="text-xl font-semibold">Describe</h1>
        <AnchorPoolLine />
        <AnchorSort preview={props.preview} />
        <SanityCount preview={props.preview} />
      </div>
      <VersionSelect version={props.version} />
      {props.version === null && <RunButton draft={props.draft} />}
    </header>
  );
}
