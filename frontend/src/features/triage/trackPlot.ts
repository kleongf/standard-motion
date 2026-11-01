// Reading a tracked Criterion's track plot: one point per 5 fps frame of the stretch it reads,
// with no value where SAM had no box.
import { padded, type TimePoint } from "../episodes/timeSeries";
import type { PlotPoint, TrackPlot } from "./useTriage";

const FRAME_S = 0.2; // a 5 fps frame, when the plot is too short to tell

/** The runs of consecutive points with a value: the line breaks where SAM had no box. */
export function plotRuns(points: PlotPoint[]): TimePoint[][] {
  const runs: TimePoint[][] = [];
  let run: TimePoint[] = [];
  for (const { t, value } of points) {
    if (value === null) {
      if (run.length) runs.push(run);
      run = [];
    } else {
      run.push({ t, value });
    }
  }
  if (run.length) runs.push(run);
  return runs;
}

/** The value on the frame showing at `t`; null outside the plot or where SAM had no box. */
export function plotValueAt(plot: TrackPlot, t: number): number | null {
  const { points } = plot;
  const first = points[0];
  const last = points[points.length - 1];
  if (!first || !last) return null;
  const step = (points[1]?.t ?? first.t + FRAME_S) - first.t;
  if (t < first.t - 1e-6 || t >= last.t + step) return null;
  const showing = points.filter((p) => p.t <= t + 1e-6).pop();
  return showing?.value ?? null;
}

/** The value range to draw: zero, every value and the level, padded a little. */
export function plotDomain(plot: TrackPlot): [number, number] {
  const values = plot.points.flatMap((p) => (p.value === null ? [] : [p.value]));
  return padded(Math.min(0, plot.level, ...values), Math.max(0, plot.level, ...values), 0.1);
}
