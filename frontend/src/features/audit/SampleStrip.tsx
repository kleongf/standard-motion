// The strip under the Audit Workstation: the whole sample in order, Keeps then Rejects, each with
// its mark and opening on click. An item whose Triage decision changed since the draw says so.
import { cn } from "@/lib/utils";

import { frame0Url } from "../boxes/useBoxes";
import type { Episode } from "../episodes/useEpisodes";
import { DECISION_LABELS } from "../triage/useTriage";
import type { AuditItem } from "./useAudit";

const MARK_TEXT: Record<"good" | "bad" | "none", string> = {
  good: "Good",
  bad: "Bad",
  none: "Not marked",
};

const MARK_CLASS: Record<"good" | "bad" | "none", string> = {
  good: "text-emerald-700 dark:text-emerald-400",
  bad: "text-red-700 dark:text-red-400",
  none: "text-muted-foreground",
};

export function SampleStrip(props: {
  items: AuditItem[];
  current: AuditItem;
  episodes: Map<string, Episode>;
  onOpen: (id: string) => void;
}) {
  return (
    <section aria-label="Sample" className="mt-6">
      <div className="mb-2 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
        Sample
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {props.items.map((item) => {
          const camera = props.episodes.get(item.episode_id)?.cameras[0];
          const mark = item.mark ?? "none";
          return (
            <button
              key={item.episode_id}
              type="button"
              aria-current={item === props.current ? "true" : undefined}
              onClick={() => {
                props.onOpen(item.episode_id);
              }}
              className={cn(
                "w-36 shrink-0 rounded p-1 text-left text-xs hover:bg-muted",
                item === props.current && "bg-muted ring-1 ring-border",
              )}
            >
              {camera ? (
                <img
                  src={frame0Url(item.episode_id, camera)}
                  alt=""
                  className="aspect-video w-full rounded bg-black object-cover"
                />
              ) : (
                <div className="aspect-video w-full rounded bg-muted" />
              )}
              <div className="mt-1 font-medium">{item.episode_id}</div>
              <div className="text-muted-foreground">
                {item.kind === "keep" ? "Keep" : "Reject"} ·{" "}
                <span className={MARK_CLASS[mark]}>{MARK_TEXT[mark]}</span>
                {item.decision !== item.kind && ` · now ${DECISION_LABELS[item.decision]}`}
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
