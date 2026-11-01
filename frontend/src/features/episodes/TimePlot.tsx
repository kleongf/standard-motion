// One plot on the Workstation's shared time axis: a line (broken into runs where there is no
// value), an optional dashed level, the hover crosshair and the playhead. Hovering reports the
// time under the pointer; clicking picks it.
import type { MouseEvent } from "react";

import type { TimePoint } from "./timeSeries";

const SERIES = "#2a78d6"; // categorical slot 1 (dataviz reference palette)
const LEVEL = "#d97706"; // the Rubric's levels, amber like its assumed values
const WIDTH = 1000;
const HEIGHT = 56;

export function TimePlot(props: {
  label: string;
  duration: number;
  runs: TimePoint[][];
  domain: [number, number];
  level?: { value: number; title: string; testId?: string } | undefined;
  playheadT: number;
  hoverT: number | null;
  onHover: (t: number | null) => void;
  onPick: (t: number) => void;
}) {
  const timeAt = (event: MouseEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    return ((event.clientX - box.left) / box.width) * props.duration;
  };
  const x = (t: number) => (t / props.duration) * WIDTH;
  const [lo, hi] = props.domain;
  const y = (v: number) => HEIGHT - 2 - ((v - lo) / (hi - lo)) * (HEIGHT - 4);
  const vertical = (t: number) => ({ x1: x(t), x2: x(t), y1: 0, y2: HEIGHT });
  return (
    <svg
      role="img"
      aria-label={props.label}
      viewBox={`0 0 ${String(WIDTH)} ${String(HEIGHT)}`}
      preserveAspectRatio="none"
      className="block h-14 w-full cursor-crosshair rounded-sm bg-muted/50"
      onPointerMove={(event) => {
        props.onHover(timeAt(event));
      }}
      onPointerLeave={() => {
        props.onHover(null);
      }}
      onClick={(event) => {
        props.onPick(timeAt(event));
      }}
    >
      {props.runs.map((run) => (
        <polyline
          key={run[0]?.t}
          points={run.map((p) => `${String(x(p.t))},${String(y(p.value))}`).join(" ")}
          fill="none"
          stroke={SERIES}
          strokeWidth={2}
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      ))}
      {props.level && (
        <line
          data-testid={props.level.testId}
          x1={0}
          x2={WIDTH}
          y1={y(props.level.value)}
          y2={y(props.level.value)}
          stroke={LEVEL}
          strokeDasharray="6 4"
          vectorEffect="non-scaling-stroke"
        >
          <title>{props.level.title}</title>
        </line>
      )}
      {props.hoverT !== null && (
        <line
          {...vertical(props.hoverT)}
          className="stroke-muted-foreground"
          strokeDasharray="3 3"
          vectorEffect="non-scaling-stroke"
        />
      )}
      <line
        {...vertical(props.playheadT)}
        className="stroke-foreground"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
