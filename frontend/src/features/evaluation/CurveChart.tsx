// A small line chart for the report's curves: Winnow and Spark alone on one 0–1 axis. A crosshair
// snaps to the nearest plotted x and reads out every series there; the numbers are also in a
// table under the chart, so nothing hides behind hover.
import { useState, type PointerEvent } from "react";

import { valueAt, type CurvePoint } from "./curves";
import type { SystemRow } from "./useEvaluation";

type System = SystemRow["system"];

export interface Series {
  system: System;
  label: string;
  points: CurvePoint[];
}

// Each system keeps its own slot of the dataviz reference palette (light and dark steps), in the
// comparison table's order, so a colour always means the same system.
const TONES: Record<System, { stroke: string; fill: string; key: string }> = {
  winnow: {
    stroke: "stroke-[#2a78d6] dark:stroke-[#3987e5]",
    fill: "fill-[#2a78d6] dark:fill-[#3987e5]",
    key: "bg-[#2a78d6] dark:bg-[#3987e5]",
  },
  spark_alone: {
    stroke: "stroke-[#eb6834] dark:stroke-[#d95926]",
    fill: "fill-[#eb6834] dark:fill-[#d95926]",
    key: "bg-[#eb6834] dark:bg-[#d95926]",
  },
  winnow_review_kept: {
    stroke: "stroke-[#1baf7a] dark:stroke-[#199e70]",
    fill: "fill-[#1baf7a] dark:fill-[#199e70]",
    key: "bg-[#1baf7a] dark:bg-[#199e70]",
  },
  length_alone: {
    stroke: "stroke-[#eda100] dark:stroke-[#c98500]",
    fill: "fill-[#eda100] dark:fill-[#c98500]",
    key: "bg-[#eda100] dark:bg-[#c98500]",
  },
};

const W = 520;
const H = 260;
const PAD = { left: 40, right: 96, top: 12, bottom: 36 };
const PLOT_W = W - PAD.left - PAD.right;
const PLOT_H = H - PAD.top - PAD.bottom;
const Y_TICKS = [0, 0.25, 0.5, 0.75, 1];

function nearestX(series: Series[], x: number): number | null {
  const xs = series.flatMap((s) => s.points.map((p) => p.x));
  if (xs.length === 0) return null;
  return xs.reduce((best, v) => (Math.abs(v - x) < Math.abs(best - x) ? v : best));
}

function Readout(props: { series: Series[]; x: number; formatX: (x: number) => string }) {
  return (
    <div className="pointer-events-none absolute top-2 left-12 rounded-md border bg-popover px-2.5 py-1.5 text-xs shadow-sm">
      <div className="text-muted-foreground">{props.formatX(props.x)}</div>
      {props.series.map((s) => {
        const point = valueAt(s.points, props.x);
        return (
          <div key={s.system} className="flex items-center gap-1.5">
            <span className={`h-0.5 w-3 rounded ${TONES[s.system].key}`} />
            <span className="font-medium tabular-nums">{point ? point.y.toFixed(2) : "–"}</span>
            <span className="text-muted-foreground">
              {s.label}
              {point ? ` · ${point.count}` : ""}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function NumbersTable(props: { series: Series[]; xLabel: string; formatX: (x: number) => string }) {
  return (
    <details className="mt-1 text-xs">
      <summary className="cursor-pointer text-muted-foreground">Show the numbers</summary>
      <table className="mt-1 w-full tabular-nums">
        <thead className="text-muted-foreground">
          <tr>
            <th className="text-left font-normal">System</th>
            <th className="text-left font-normal">{props.xLabel}</th>
            <th className="text-left font-normal">Counts</th>
          </tr>
        </thead>
        <tbody>
          {props.series.flatMap((s) =>
            s.points.map((p) => (
              <tr key={`${s.system}-${String(p.x)}`}>
                <td>{s.label}</td>
                <td>{props.formatX(p.x)}</td>
                <td>{p.count}</td>
              </tr>
            )),
          )}
        </tbody>
      </table>
    </details>
  );
}

/** Direct labels at each line's end, nudged apart when they would overlap. */
function endLabels(series: Series[], y: (v: number) => number) {
  const ends = series
    .filter((s) => s.points.length > 0)
    .map((s) => ({ s, at: y(s.points.at(-1)?.y ?? 0) }));
  return ends.map((end, i) => {
    const previous = ends[i - 1];
    const clash = previous !== undefined && Math.abs(previous.at - end.at) < 14;
    return { ...end, at: clash ? previous.at + 14 : end.at };
  });
}

export function CurveChart(props: {
  title: string;
  series: Series[];
  xMax: number;
  xLabel: string;
  yLabel: string;
  formatX: (x: number) => string;
  marker?: { x: number; label: string } | null;
  empty: string;
}) {
  const [hoverX, setHoverX] = useState<number | null>(null);
  const x = (v: number) => PAD.left + (v / props.xMax) * PLOT_W;
  const y = (v: number) => PAD.top + (1 - v) * PLOT_H;
  const xTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * props.xMax);
  const plotted = props.series.some((s) => s.points.length > 0);
  const onMove = (event: PointerEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    const px = ((event.clientX - box.left) / box.width) * W;
    setHoverX(nearestX(props.series, ((px - PAD.left) / PLOT_W) * props.xMax));
  };
  return (
    <figure className="relative">
      <div className="mb-1 flex items-center gap-3 text-xs text-muted-foreground">
        {props.series.map((s) => (
          <span key={s.system} className="flex items-center gap-1.5">
            <span className={`h-0.5 w-3 rounded ${TONES[s.system].key}`} />
            {s.label}
          </span>
        ))}
      </div>
      <svg
        role="img"
        aria-label={props.title}
        viewBox={`0 0 ${String(W)} ${String(H)}`}
        className="block w-full"
        onPointerMove={onMove}
        onPointerLeave={() => {
          setHoverX(null);
        }}
      >
        {Y_TICKS.map((t) => (
          <g key={t}>
            <line
              x1={PAD.left}
              x2={PAD.left + PLOT_W}
              y1={y(t)}
              y2={y(t)}
              className="stroke-border"
            />
            <text
              x={PAD.left - 6}
              y={y(t) + 3}
              textAnchor="end"
              className="fill-muted-foreground text-[10px]"
            >
              {t.toFixed(2)}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text
            key={t}
            x={x(t)}
            y={PAD.top + PLOT_H + 14}
            textAnchor="middle"
            className="fill-muted-foreground text-[10px]"
          >
            {props.formatX(t)}
          </text>
        ))}
        <text
          x={PAD.left + PLOT_W / 2}
          y={H - 4}
          textAnchor="middle"
          className="fill-muted-foreground text-[11px]"
        >
          {props.xLabel}
        </text>
        <text
          transform={`translate(10 ${String(PAD.top + PLOT_H / 2)}) rotate(-90)`}
          textAnchor="middle"
          className="fill-muted-foreground text-[11px]"
        >
          {props.yLabel}
        </text>
        {props.marker && (
          <g data-testid="curve-marker">
            <line
              x1={x(props.marker.x)}
              x2={x(props.marker.x)}
              y1={PAD.top}
              y2={PAD.top + PLOT_H}
              className="stroke-muted-foreground"
            />
            <text
              x={x(props.marker.x) + 4}
              y={PAD.top + 10}
              className="fill-muted-foreground text-[10px]"
            >
              {props.marker.label}
            </text>
          </g>
        )}
        {props.series.map((s) => (
          <g key={s.system} data-testid={`curve-${s.system}`}>
            <polyline
              points={s.points.map((p) => `${String(x(p.x))},${String(y(p.y))}`).join(" ")}
              fill="none"
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
              className={TONES[s.system].stroke}
            />
            {s.points.map((p) => (
              <circle
                key={p.x}
                cx={x(p.x)}
                cy={y(p.y)}
                r={4}
                strokeWidth={2}
                className={`${TONES[s.system].fill} stroke-background`}
              />
            ))}
          </g>
        ))}
        {endLabels(props.series, y).map(({ s, at }) => (
          <text
            key={s.system}
            x={PAD.left + PLOT_W + 8}
            y={at + 3}
            className="fill-foreground text-[11px]"
          >
            {s.label}
          </text>
        ))}
        {hoverX !== null && (
          <line
            x1={x(hoverX)}
            x2={x(hoverX)}
            y1={PAD.top}
            y2={PAD.top + PLOT_H}
            className="stroke-foreground/40"
          />
        )}
        {!plotted && (
          <text
            x={PAD.left + PLOT_W / 2}
            y={PAD.top + PLOT_H / 2}
            textAnchor="middle"
            className="fill-muted-foreground text-[12px]"
          >
            {props.empty}
          </text>
        )}
      </svg>
      {hoverX !== null && <Readout series={props.series} x={hoverX} formatX={props.formatX} />}
      <NumbersTable series={props.series} xLabel={props.xLabel} formatX={props.formatX} />
    </figure>
  );
}
