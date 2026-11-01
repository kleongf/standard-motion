// One Criterion result in the Workstation panel: the rendered English over its status pill and
// measurement; opened, why it is uncertain, its Phrase, Evidence, kind, hard or soft, p, window
// and moment pills.
import { ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";

import { VisualEvidence } from "../visual/VisualEvidence";
import { Pill, StatusPill } from "./Pill";
import { SeekableText } from "./SeekableText";
import type { CriterionResult } from "./useTriage";

function windowText(r: CriterionResult): string {
  if (!r.window) return `${r.window_name}: empty`;
  return `${r.window_name}, ${r.window.start.toFixed(1)}–${r.window.end.toFixed(1)} s`;
}

export function CriterionResultRow(props: {
  episodeId: string;
  result: CriterionResult;
  open: boolean;
  onToggle: () => void;
  onSeek: (t: number) => void;
}) {
  const r = props.result;
  return (
    <div className="border-t py-2" data-testid={`criterion-${r.criterion_id}`}>
      <button
        type="button"
        aria-expanded={props.open}
        onClick={props.onToggle}
        className="group grid w-full grid-cols-[minmax(0,1fr)_0.75rem] items-start gap-x-2 text-left"
      >
        <span
          className={cn(
            "text-[13px] leading-snug text-balance group-hover:text-primary",
            !props.open && "line-clamp-2",
          )}
        >
          {r.english}
        </span>
        <ChevronRight
          className={cn(
            "mt-0.5 size-3 text-muted-foreground/60 transition-transform",
            props.open && "rotate-90",
          )}
        />
        <span className="mt-1 flex items-center gap-1.5">
          <StatusPill status={r.status} />
          <span className="truncate text-xs font-semibold tabular-nums">{r.measurement}</span>
        </span>
      </button>
      {props.open && <Opened result={r} episodeId={props.episodeId} onSeek={props.onSeek} />}
    </div>
  );
}

function Opened(props: {
  episodeId: string;
  result: CriterionResult;
  onSeek: (t: number) => void;
}) {
  const r = props.result;
  return (
    <div className="mt-2 grid gap-2 border-l-2 pl-3 text-[13px] leading-snug">
      {r.uncertainty && (
        <div>
          <Pill tone="warning">{r.uncertainty}</Pill>
        </div>
      )}
      <div className="font-medium">“{r.phrase}”</div>
      <p className="text-foreground/85">
        <SeekableText spans={r.evidence} onSeek={props.onSeek} />
      </p>
      <div className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground tabular-nums">
        <Pill tone="neutral">{r.kind}</Pill>
        <Pill tone="neutral">{r.hard ? "hard" : "soft"}</Pill>
        <span className="ml-1" title="How likely this Criterion passes">
          p <span className="font-semibold text-foreground">{r.p_pass.toFixed(2)}</span>
        </span>
      </div>
      <div className="text-xs text-muted-foreground tabular-nums">Window: {windowText(r)}</div>
      {r.visual && <VisualEvidence episodeId={props.episodeId} visual={r.visual} />}
      {r.moments.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {r.moments.map((m) => (
            <button
              key={`${m.label}-${String(m.t)}`}
              type="button"
              aria-label={`${m.label} ${m.t.toFixed(1)} s`}
              onClick={() => {
                props.onSeek(m.t);
              }}
              className="inline-flex h-6 items-center gap-1.5 rounded-full border bg-background px-2.5 text-xs font-medium transition-colors hover:border-primary/50 hover:bg-primary/5 hover:text-primary"
            >
              {m.label}
              <span className="text-muted-foreground tabular-nums">{m.t.toFixed(1)} s</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
