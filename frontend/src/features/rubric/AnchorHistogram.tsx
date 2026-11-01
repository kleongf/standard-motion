// A Criterion's anchor-pool values as a histogram stacked by status, with its threshold, the
// margin band around it, any threshold labels suggest (dashed), and (when editable) a slider to
// drag the threshold over it.
import { Slider } from "@/components/ui/slider";

import { binValues, formatValue, sliderDomain } from "./histogram";
import type { CriterionPreview } from "./useDraftEdits";

const WIDTH = 300;
const HEIGHT = 56;

const FILLS = {
  pass: "fill-emerald-500/80",
  unsure: "fill-amber-400/90",
  fail: "fill-rose-500/80",
} as const;

export function AnchorHistogram(props: {
  preview: CriterionPreview;
  threshold: number; // shown, maybe mid-drag
  anchor: number; // the saved threshold, which fixes the range while dragging
  label: string;
  suggested?: number | undefined; // a threshold the labels suggest
  onDrag?: ((threshold: number) => void) | undefined;
  onCommit?: ((threshold: number) => void) | undefined;
}) {
  const { preview, threshold } = props;
  const measured = preview.values.flatMap((v) => (v.value === null ? [] : [v.value]));
  const unmeasured = preview.values.length - measured.length;
  // The range follows the values and the saved threshold, never the drag.
  const domain = sliderDomain(measured, props.anchor, preview.margin, preview.unit);
  const bins = binValues(preview.values, domain);
  const tallest = Math.max(1, ...bins.map((b) => b.pass + b.fail + b.unsure));
  const x = (v: number) => ((v - domain.min) / (domain.max - domain.min)) * WIDTH;
  const lo = x(threshold - preview.margin);
  const hi = x(threshold + preview.margin);
  return (
    <div className="mt-2">
      <svg
        viewBox={`0 0 ${String(WIDTH)} ${String(HEIGHT)}`}
        className="h-14 w-full overflow-visible"
        role="img"
        aria-label={`Anchor-pool values against ${formatValue(threshold, preview.unit)}`}
        preserveAspectRatio="none"
      >
        {preview.margin > 0 && (
          <rect
            x={Math.max(0, lo)}
            width={Math.max(0, Math.min(WIDTH, hi) - Math.max(0, lo))}
            y={0}
            height={HEIGHT}
            className="fill-amber-300/25"
            data-testid="margin-band"
          />
        )}
        {bins.map((bin) => {
          const left = x(bin.start) + 1;
          const width = Math.max(1, x(bin.end) - x(bin.start) - 2);
          let top = HEIGHT;
          return (["pass", "unsure", "fail"] as const).map((status) => {
            const h = (bin[status] / tallest) * (HEIGHT - 4);
            top -= h;
            return h > 0 ? (
              <rect
                key={`${String(bin.start)}-${status}`}
                x={left}
                y={top}
                width={width}
                height={h}
                className={FILLS[status]}
              />
            ) : null;
          });
        })}
        {props.suggested !== undefined && (
          <line
            x1={x(props.suggested)}
            x2={x(props.suggested)}
            y1={0}
            y2={HEIGHT}
            className="stroke-sky-600 dark:stroke-sky-400"
            strokeWidth={1.5}
            strokeDasharray="3 2"
            vectorEffect="non-scaling-stroke"
            data-testid="suggested-line"
          />
        )}
        <line
          x1={x(threshold)}
          x2={x(threshold)}
          y1={0}
          y2={HEIGHT}
          className="stroke-foreground"
          strokeWidth={1.5}
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="flex justify-between text-[10px] text-muted-foreground tabular-nums">
        <span>{formatValue(domain.min, preview.unit)}</span>
        {unmeasured > 0 && <span>{unmeasured} not measured, so unsure</span>}
        <span>{formatValue(domain.max, preview.unit)}</span>
      </div>
      {props.onDrag && (
        <Slider
          className="mt-1"
          aria-label={props.label}
          min={domain.min}
          max={domain.max}
          step={domain.step}
          value={[threshold]}
          onValueChange={([v]) => {
            if (v !== undefined) props.onDrag?.(v);
          }}
          onValueCommit={([v]) => {
            if (v !== undefined) props.onCommit?.(v);
          }}
        />
      )}
    </div>
  );
}
