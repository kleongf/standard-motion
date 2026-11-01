// A threshold the labels suggest for one Criterion, on its card: only accepting it, as a new
// Rubric version, moves the threshold.
import { Lightbulb } from "lucide-react";

import { Button } from "@/components/ui/button";

import type { ThresholdSuggestion } from "./useCalibration";

export interface SuggestionAction {
  suggestion: ThresholdSuggestion;
  nextVersion: number;
  pending: boolean;
  onAccept: () => void;
}

export function SuggestionNote(props: { action: SuggestionAction }) {
  const { suggestion, nextVersion, pending, onAccept } = props.action;
  return (
    <div
      className="mt-2 flex items-start gap-2 rounded border border-sky-200 bg-sky-50 px-2 py-1.5 text-xs text-sky-950 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-100"
      data-testid="threshold-suggestion"
    >
      <Lightbulb className="mt-0.5 size-3.5 shrink-0" />
      <div className="min-w-0 flex-1">
        <span className="mr-1.5 rounded bg-sky-200/70 px-1 font-medium dark:bg-sky-800/60">
          Labels suggest
        </span>
        {suggestion.suggested_english}
        <div className="mt-0.5 text-sky-900/80 dark:text-sky-200/80">
          {suggestion.contradicting} of {suggestion.labelled} labels contradict it now; midway
          between the closest labelled pass and fail.
        </div>
      </div>
      <Button size="xs" disabled={pending} onClick={onAccept}>
        {pending ? "Accepting…" : `Accept as v${String(nextVersion)}`}
      </Button>
    </div>
  );
}
