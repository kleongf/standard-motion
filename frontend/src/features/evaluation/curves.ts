// The report's curves as plottable points, each keeping its counts for the tooltip and table.
import type { RightReasonRow, RiskCoverage } from "./useEvaluation";

export interface CurvePoint {
  x: number;
  y: number;
  count: string;
}

/** Risk (errors among the covered) against coverage (covered of every labelled Episode). */
export function riskSeries(curve: RiskCoverage): CurvePoint[] {
  return curve.points.map((p) => ({
    x: p.covered / curve.episodes,
    y: p.errors / p.covered,
    count: `${String(p.errors)} wrong of ${String(p.covered)}`,
  }));
}

/** The share of correct Rejects whose Reason is right, against slack; empty with none. */
export function slackSeries(row: RightReasonRow): CurvePoint[] {
  return row.curve
    .filter((p) => p.of > 0)
    .map((p) => ({
      x: p.slack_s,
      y: p.right / p.of,
      count: `${String(p.right)} of ${String(p.of)}`,
    }));
}

/** A curve's value at `x`: its last point at or before it. */
export function valueAt(points: CurvePoint[], x: number): CurvePoint | undefined {
  return points.filter((p) => p.x <= x + 1e-9).at(-1);
}
