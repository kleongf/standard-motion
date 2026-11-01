// Triage decisions and Criterion statuses, coloured the same everywhere: green passes and keeps,
// red fails and rejects, amber is unsure and needs review.
import { cn } from "@/lib/utils";

import { DECISION_LABELS, type Status, type TriageDecision } from "./useTriage";

const DECISION_CLASSES: Record<TriageDecision, string> = {
  keep: "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  reject:
    "border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300",
  needs_review:
    "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300",
};

export const STATUS_TEXT: Record<Status, string> = {
  pass: "text-emerald-700 dark:text-emerald-400",
  fail: "text-red-700 dark:text-red-400",
  unsure: "text-amber-700 dark:text-amber-400",
};

/** Small chips for a Phrase that failed or is unsure. */
export const STATUS_CHIP: Record<"fail" | "unsure", string> = {
  fail: DECISION_CLASSES.reject,
  unsure: DECISION_CLASSES.needs_review,
};

export const STATUS_FILL: Record<Status, string> = {
  pass: "bg-emerald-600",
  fail: "bg-red-600",
  unsure: "bg-amber-500",
};

export function TriageBadge(props: { decision: TriageDecision; className?: string }) {
  return (
    <span
      data-testid="triage-decision"
      className={cn(
        "inline-block rounded border px-1.5 py-0.5 text-xs font-medium whitespace-nowrap",
        DECISION_CLASSES[props.decision],
        props.className,
      )}
    >
      {DECISION_LABELS[props.decision]}
    </span>
  );
}
