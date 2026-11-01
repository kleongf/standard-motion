// Robot-data plots on the Workstation's shared time axis. One series each, so no legend: the
// header names it and reads out its value at the hovered time (else at the playhead).
// Hovering one plot draws the crosshair on all of them; clicking seeks.
import { useState } from "react";

import { padded } from "./timeSeries";
import { TimePlot } from "./TimePlot";
import type { Playhead } from "./usePlayhead";
import type { Signals } from "./useEpisodes";

type Key = "gripper" | "z" | "speed";

const PLOTS: { key: Key; label: string; unit: string; digits: number; fixed?: [number, number] }[] =
  [
    { key: "gripper", label: "Gripper", unit: "0 open · 1 closed", digits: 2, fixed: [0, 1] },
    { key: "z", label: "Height", unit: "m", digits: 3 },
    { key: "speed", label: "Speed", unit: "m/s", digits: 3 },
  ];

function domain(values: number[], fixed?: [number, number]): [number, number] {
  return fixed ?? padded(Math.min(...values), Math.max(...values), 0.01);
}

export function valueAt(signals: Signals, key: Key, t: number): number | undefined {
  const step = signals.t[1] ?? 0;
  const index = step > 0 ? Math.round(t / step) : 0;
  return signals[key][Math.max(0, Math.min(signals[key].length - 1, index))];
}

export function SignalPlots(props: {
  signals: Signals;
  playhead: Playhead;
  duration: number;
  /** A dashed reference line per plot, e.g. the Rubric's gripper-closed level. */
  levels?: Partial<Record<Key, number>>;
}) {
  const [hoverT, setHoverT] = useState<number | null>(null);
  const readT = hoverT ?? props.playhead.t;
  return (
    <div className="mt-3 grid gap-2.5">
      {PLOTS.map((plot) => {
        const values = props.signals[plot.key];
        const value = valueAt(props.signals, plot.key, readT);
        const level = props.levels?.[plot.key];
        const run = values.map((v, i) => ({ t: props.signals.t[i] ?? 0, value: v }));
        return (
          <div key={plot.key}>
            <div className="mb-0.5 flex items-baseline gap-1.5 text-[11px]">
              <span className="text-muted-foreground">{plot.label}</span>
              <span
                className="ml-auto font-medium tabular-nums"
                data-testid={`readout-${plot.key}`}
              >
                {value?.toFixed(plot.digits)}
              </span>
              <span className="text-muted-foreground">
                {plot.unit} · {readT.toFixed(1)} s
              </span>
            </div>
            <TimePlot
              label={`${plot.label} over the Episode`}
              duration={props.duration}
              runs={[run]}
              domain={domain(values, plot.fixed)}
              level={
                level === undefined
                  ? undefined
                  : {
                      value: level,
                      title: `${plot.label} level ${String(level)}`,
                      testId: `level-${plot.key}`,
                    }
              }
              playheadT={props.playhead.t}
              hoverT={hoverT}
              onHover={setHoverT}
              onPick={props.playhead.seek}
            />
          </div>
        );
      })}
    </div>
  );
}
