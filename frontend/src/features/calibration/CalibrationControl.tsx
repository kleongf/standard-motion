// The Calibrate control on the Rubric version in use: the margin multiplier s it is scored with,
// how many labels tuned it, and why to label more. Tuned on labels, never a guarantee.
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";

import { sText, multiplierLine, warnings } from "./calibrationText";
import { type Calibration, useRunCalibration } from "./useCalibration";

function Contradicted(props: { calibration: Calibration }) {
  const { record } = props.calibration;
  if (!record) return null;
  return (
    <p className="mt-1 text-xs text-muted-foreground tabular-nums">
      At s = {sText(record.s)}, {record.errors} of {record.n_labels} labelled Phrases had a crisp
      result their label contradicts.
    </p>
  );
}

export function CalibrationControl(props: { calibration: Calibration }) {
  const { calibration } = props;
  const run = useRunCalibration();
  const shown = warnings(calibration.record, calibration.max_error_rate, calibration.confidence);
  return (
    <section
      aria-label="Calibration"
      className="mt-3 rounded-lg border bg-card p-3"
      data-testid="calibration"
    >
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
            Margin multiplier
          </div>
          <p className="text-sm font-medium tabular-nums" data-testid="multiplier">
            {multiplierLine(calibration.s, calibration.record)}
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          disabled={run.isPending || calibration.labelled === 0}
          onClick={() => {
            run.mutate();
          }}
        >
          {run.isPending ? "Calibrating…" : calibration.record ? "Calibrate again" : "Calibrate"}
        </Button>
      </div>
      <Contradicted calibration={calibration} />
      {calibration.labelled === 0 && (
        <p className="mt-1 text-xs text-muted-foreground">
          No interview or review labels on the anchor pool yet: answer the interview or review
          Episodes to calibrate.
        </p>
      )}
      {shown.map((warning) => (
        <p
          key={warning}
          className="mt-2 flex items-start gap-1.5 rounded bg-amber-50 px-2 py-1 text-xs text-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
          data-testid="calibration-warning"
        >
          <AlertTriangle className="mt-0.5 size-3 shrink-0" />
          <span>{warning}</span>
        </p>
      ))}
      {run.error && <p className="mt-2 text-xs text-destructive">{run.error.message}</p>}
      <p className="mt-2 text-[11px] text-muted-foreground">
        Every margin is max(noise floor, interview gap) × s, tuned on the Dev set’s interview and
        review labels. A new Rubric version from Run starts at s = 1.0 until it is calibrated; one
        made by accepting a suggestion keeps this s.
      </p>
    </section>
  );
}
