// Review's link back to the Rubric: once answers here could move the margins (labels since the last
// calibration) or suggest a threshold, say so, and recalibrate from here; suggestions are accepted
// on Describe & run, as a new Rubric version.
import { Button } from "@/components/ui/button";

import { goTo } from "../core/pages";
import { useRubric } from "../rubric/useRubric";
import { sText } from "./calibrationText";
import { type Calibration, useCalibration, useRunCalibration } from "./useCalibration";

function plural(n: number, word: string): string {
  return `${String(n)} ${word}${n === 1 ? "" : "s"}`;
}

/** What answers since the last calibration could change, or null when nothing could. */
function loopSummary(c: Calibration): { fresh: number; suggested: number; text: string } | null {
  const fresh = c.labelled - (c.record?.n_labels ?? 0);
  const suggested = c.suggestions.length;
  const parts = [
    fresh > 0 && `${plural(fresh, "new label")} since s = ${sText(c.s)} was tuned`,
    suggested > 0 && plural(suggested, "threshold suggestion"),
  ].filter(Boolean);
  return parts.length > 0 ? { fresh, suggested, text: parts.join(" · ") } : null;
}

export function LoopNote() {
  const calibration = useCalibration(useRubric().data?.version).data;
  const summary = calibration && loopSummary(calibration);
  if (!summary) return null;
  return (
    <section
      aria-label="Your answers and the Rubric"
      className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-primary/30 bg-primary/5 px-4 py-2.5 text-sm"
    >
      <span className="min-w-0 flex-1 font-medium">{summary.text}</span>
      {summary.fresh > 0 && <RecalibrateButton />}
      {summary.suggested > 0 && (
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            goTo("describe");
          }}
        >
          Review suggestions
        </Button>
      )}
    </section>
  );
}

function RecalibrateButton() {
  const run = useRunCalibration();
  return (
    <>
      <Button
        size="sm"
        disabled={run.isPending}
        onClick={() => {
          run.mutate();
        }}
      >
        {run.isPending ? "Calibrating…" : "Recalibrate"}
      </Button>
      {run.isError && <p className="w-full text-xs text-destructive">{run.error.message}</p>}
    </>
  );
}
