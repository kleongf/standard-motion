// Soft pills for values that are categories: the Triage decision, a Criterion status, why a result
// is uncertain, neutral facts (kind, hard or soft, Set) and warnings. Measurements stay plain text.
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { DECISION_LABELS, type Status, type TriageDecision } from "./useTriage";

type Tone = Status | "neutral" | "warning";

const TONE: Record<Tone, string> = {
  pass: "bg-emerald-500/12 text-emerald-800 ring-1 ring-emerald-600/20 ring-inset dark:bg-emerald-400/15 dark:text-emerald-300 dark:ring-emerald-400/25",
  fail: "bg-red-500/10 text-red-800 ring-1 ring-red-600/20 ring-inset dark:bg-red-400/15 dark:text-red-300 dark:ring-red-400/25",
  unsure:
    "bg-amber-500/15 text-amber-800 ring-1 ring-amber-600/25 ring-inset dark:bg-amber-400/15 dark:text-amber-300 dark:ring-amber-400/25",
  neutral: "bg-muted text-muted-foreground",
  warning: "bg-amber-500/12 text-amber-800 dark:bg-amber-400/15 dark:text-amber-300",
};

const DOT: Record<Status, string> = {
  pass: "bg-emerald-500",
  fail: "bg-red-500",
  unsure: "bg-amber-500",
};

const DECISION_TONE: Record<TriageDecision, Status> = {
  keep: "pass",
  reject: "fail",
  needs_review: "unsure",
};

export function Pill(props: {
  tone: Tone;
  children: ReactNode;
  title?: string | undefined;
  className?: string | undefined;
}) {
  return (
    <span
      title={props.title}
      className={cn(
        "inline-flex h-5 shrink-0 items-center gap-1 rounded-full px-2 text-[11px] font-medium whitespace-nowrap",
        TONE[props.tone],
        props.className,
      )}
    >
      {props.children}
    </span>
  );
}

/** The panel's Triage decision: a dot and the word, tinted by outcome. */
export function DecisionPill(props: { decision: TriageDecision }) {
  const tone = DECISION_TONE[props.decision];
  return (
    <span
      data-testid="triage-decision"
      className={cn(
        "inline-flex h-7 items-center gap-1.5 rounded-full px-2.5 text-sm font-semibold whitespace-nowrap",
        TONE[tone],
      )}
    >
      <span className={cn("size-1.5 rounded-full", DOT[tone])} />
      {DECISION_LABELS[props.decision]}
    </span>
  );
}

export function StatusPill(props: { status: Status }) {
  return (
    <Pill tone={props.status} className="font-semibold capitalize">
      {props.status}
    </Pill>
  );
}

/** How many Criterion results fail, are unsure and pass, as counted dots. */
export function StatusCounts(props: { statuses: Status[] }) {
  const order: Status[] = ["fail", "unsure", "pass"];
  return (
    <span className="flex gap-1">
      {order.map((status) => {
        const n = props.statuses.filter((s) => s === status).length;
        if (n === 0) return null;
        return (
          <Pill
            key={status}
            tone={status}
            title={`${String(n)} ${status}`}
            className="h-[18px] px-1.5 text-[10px] font-semibold tabular-nums"
          >
            <span className={cn("size-1.5 rounded-full", DOT[status])} />
            {n}
          </Pill>
        );
      })}
    </span>
  );
}
