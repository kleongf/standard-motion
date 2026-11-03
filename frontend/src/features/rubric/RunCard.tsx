// What Run did, as Spark's last turn: the frozen version, and how it sorted the Episodes it can
// show (those with a Reference label), once the Triage list is scored against it.
import { ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { goTo } from "../core/pages";
import { DECISION_LABELS, type TriageDecision, useTriageList } from "../triage/useTriage";

const TILES: { decision: TriageDecision; tone: string }[] = [
  {
    decision: "keep",
    tone: "bg-emerald-500/10 text-emerald-800 dark:bg-emerald-400/10 dark:text-emerald-300",
  },
  {
    decision: "reject",
    tone: "bg-red-500/10 text-red-800 dark:bg-red-400/10 dark:text-red-300",
  },
  {
    decision: "needs_review",
    tone: "bg-amber-500/12 text-amber-800 dark:bg-amber-400/10 dark:text-amber-300",
  },
];

function Counts(props: { version: number }) {
  const list = useTriageList().data;
  if (list?.rubric_version !== props.version) {
    return <p className="mt-3 text-sm text-muted-foreground">Scoring the Episodes…</p>;
  }
  const count = (d: TriageDecision) => list.rows.filter((r) => r.decision === d).length;
  if (list.rows.length === 0) {
    return (
      <p className="mt-3 text-sm text-muted-foreground">No Episode has a Reference label yet.</p>
    );
  }
  return (
    <div className="mt-3 grid grid-cols-3 gap-2">
      {TILES.map((t) => (
        <div key={t.decision} className={cn("rounded-lg px-3 py-2.5", t.tone)}>
          <p className="text-2xl font-semibold tabular-nums">{count(t.decision)}</p>
          <p className="text-xs font-medium">{DECISION_LABELS[t.decision]}</p>
        </div>
      ))}
    </div>
  );
}

export function RunCard(props: { version: number }) {
  return (
    <section aria-label="Run" className="rounded-xl border bg-card p-4 shadow-sm">
      <p className="font-medium">Rubric v{props.version} ran</p>
      <Counts version={props.version} />
      <div className="mt-3 flex justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            goTo("review");
          }}
        >
          Review
        </Button>
        <Button
          size="sm"
          onClick={() => {
            goTo("episodes");
          }}
        >
          Open Episodes
          <ArrowRight data-icon="inline-end" />
        </Button>
      </div>
    </section>
  );
}
