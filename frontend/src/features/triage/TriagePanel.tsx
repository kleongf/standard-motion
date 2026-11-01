// The top of the Workstation's right panel: the Triage decision, its confidence and quality, its
// Reason on one line (times in it seek, marked when Spark wrote it), and the Criterion results,
// expandable to their Evidence and moments.
import { Sparkles } from "lucide-react";

import { ClampedReason } from "./ClampedReason";
import { CriterionResultRow } from "./CriterionResultRow";
import { formatQuality, QUALITY_TITLE } from "./formatQuality";
import { DecisionPill, Pill, StatusCounts } from "./Pill";
import { useQuality, type CriterionResult, type EpisodeTriage } from "./useTriage";

/** The panel's small section label. */
export const PANEL_LABEL =
  "text-[11px] font-semibold tracking-wide text-muted-foreground uppercase";

export function TriagePanel(props: {
  triage: EpisodeTriage;
  openId: string | null;
  onOpen: (id: string | null) => void;
  /** Open a result on its camera and seek to `t`, or to its own moment. */
  onFocus: (result: CriterionResult, t?: number) => void;
  onSeek: (t: number) => void;
}) {
  const { triage, openId } = props;
  const unchecked = triage.phrases.filter((p) => p.status === null);
  const quality = useQuality(triage.episode_id);
  return (
    <section aria-label="Triage" className="flex flex-col gap-4">
      <div>
        <div className="flex items-center gap-2">
          <DecisionPill decision={triage.decision} />
          <span className="ml-auto text-xs text-muted-foreground">
            <span className="text-sm font-semibold text-foreground tabular-nums">
              {triage.confidence.toFixed(2)}
            </span>{" "}
            confidence
          </span>
        </div>
        {quality !== null && (
          <p
            className="mt-1 text-xs text-muted-foreground tabular-nums"
            data-testid="quality"
            title={QUALITY_TITLE}
          >
            Quality {formatQuality(quality)} · from soft Criteria, relative to the run
          </p>
        )}
        <ClampedReason spans={triage.reason} onSeek={props.onSeek} />
        {triage.reason_source === "spark" && (
          <p
            className="mt-1 inline-flex items-center gap-1 text-xs text-muted-foreground"
            data-testid="reason-source"
            title="Spark rewrote the template Reason from this Episode's Evidence"
          >
            <Sparkles aria-hidden className="size-3" />
            written by Spark
          </p>
        )}
      </div>
      <div>
        <div className="mb-1 flex items-center justify-between">
          <span className={PANEL_LABEL}>Criteria</span>
          <StatusCounts statuses={triage.criteria.map((r) => r.status)} />
        </div>
        {triage.criteria.map((r) => (
          <CriterionResultRow
            key={r.criterion_id}
            episodeId={triage.episode_id}
            result={r}
            open={openId === r.criterion_id}
            onToggle={() => {
              props.onOpen(openId === r.criterion_id ? null : r.criterion_id);
            }}
            onSeek={(t) => {
              props.onFocus(r, t);
            }}
          />
        ))}
        {unchecked.length > 0 && (
          <div className="flex flex-wrap items-center gap-1 border-t pt-2">
            <span className="text-[11px] text-muted-foreground">Not checked</span>
            {unchecked.map((p) => (
              <Pill key={p.phrase} tone="neutral">
                “{p.phrase}”
              </Pill>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
