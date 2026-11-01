// Each tracked Criterion's track plot on the Workstation's time axis: the signal it is decided on
// (e.g. the object's distance from the fingers), with the line it is judged against. The line
// breaks where SAM had no box. Hovering one plot draws the crosshair on all of them; clicking
// opens its result on its view, at that time.
import { useState } from "react";

import { TimePlot } from "../episodes/TimePlot";
import type { Playhead } from "../episodes/usePlayhead";
import { plotDomain, plotRuns, plotValueAt } from "./trackPlot";
import type { CriterionResult } from "./useTriage";

export function TrackPlots(props: {
  results: CriterionResult[];
  playhead: Playhead;
  duration: number;
  onFocus: (result: CriterionResult, t: number) => void;
}) {
  const [hoverT, setHoverT] = useState<number | null>(null);
  const plotted = props.results.flatMap((r) => (r.track_plot ? [{ r, plot: r.track_plot }] : []));
  if (!plotted.length) return null;
  const readT = hoverT ?? props.playhead.t;
  return (
    <div className="mt-3 grid gap-2.5" aria-label="Track plots">
      {plotted.map(({ r, plot }) => {
        const value = plotValueAt(plot, readT);
        return (
          <div key={r.criterion_id} data-testid={`track-plot-${r.criterion_id}`}>
            <div className="mb-0.5 flex items-baseline gap-1.5 text-[11px]">
              <span className="truncate text-muted-foreground">
                {plot.label} · {r.primitive}
              </span>
              <span className="ml-auto font-medium tabular-nums" data-testid="track-plot-readout">
                {value === null ? "—" : value.toFixed(2)}
              </span>
              <span className="text-muted-foreground">
                {plot.unit} · {readT.toFixed(1)} s
              </span>
            </div>
            <TimePlot
              label={`${plot.label}, for ${r.english}`}
              duration={props.duration}
              runs={plotRuns(plot.points)}
              domain={plotDomain(plot)}
              level={{
                value: plot.level,
                title: `Judged against ${String(plot.level)} ${plot.unit}`,
              }}
              playheadT={props.playhead.t}
              hoverT={hoverT}
              onHover={setHoverT}
              onPick={(t) => {
                props.onFocus(r, t);
              }}
            />
          </div>
        );
      })}
    </div>
  );
}
