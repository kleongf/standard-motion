// A lane per Criterion on the Workstation's time axis: its window, its Evidence moments and its
// status colour. Clicking a lane opens its result and seeks to its moment.
import { cn } from "@/lib/utils";

import { lanePercent } from "./laneFocus";
import { STATUS_FILL, STATUS_TEXT } from "./TriageBadge";
import type { CriterionResult } from "./useTriage";

export function CriterionLanes(props: {
  results: CriterionResult[];
  duration: number;
  t: number;
  openId: string | null;
  onFocus: (result: CriterionResult) => void;
}) {
  const pct = (t: number) => lanePercent(t, props.duration);
  return (
    <div className="mt-1 grid gap-1.5" aria-label="Criterion lanes">
      {props.results.map((r) => (
        <button
          key={r.criterion_id}
          type="button"
          aria-label={`Lane: ${r.english}, ${r.status}`}
          title={`${r.english}: ${r.measurement}`}
          onClick={() => {
            props.onFocus(r);
          }}
          className={cn(
            "block w-full rounded-sm text-left hover:bg-muted/60",
            props.openId === r.criterion_id && "bg-muted",
          )}
        >
          {/* Labelled above the bar, like the plots, so lanes and plots share one time axis. */}
          <span className="mb-0.5 flex items-baseline gap-1.5 text-[11px]">
            <span className="truncate text-muted-foreground">
              {r.primitive}
              {!r.hard && " · soft"}
            </span>
            <span className={cn("ml-auto font-medium", STATUS_TEXT[r.status])}>{r.status}</span>
            <span className="text-muted-foreground tabular-nums">{r.measurement}</span>
          </span>
          <span className="relative block h-4 rounded-sm bg-muted/50">
            {r.window && (
              <span
                className={cn("absolute top-1.5 h-1 opacity-40", STATUS_FILL[r.status])}
                style={{
                  left: pct(r.window.start),
                  width: `calc(${pct(r.window.end)} - ${pct(r.window.start)})`,
                }}
              />
            )}
            {r.moments.map((m) => (
              <span
                key={`${m.label}-${String(m.t)}`}
                title={`${m.label} · ${m.t.toFixed(1)} s`}
                className={cn("absolute top-px h-3.5 w-[3px] rounded-full", STATUS_FILL[r.status])}
                style={{ left: pct(m.t) }}
              />
            ))}
            <span
              className="absolute inset-y-0 w-px bg-foreground"
              style={{ left: pct(props.t) }}
            />
          </span>
        </button>
      ))}
    </div>
  );
}
