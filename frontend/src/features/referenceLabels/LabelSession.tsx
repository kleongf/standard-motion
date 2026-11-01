// Labelling one Episode of a queue: the Workstation with every output hidden and the label
// panel in its actions slot. Save & next (or Skip) opens the next Episode left; Esc goes back.
import { useEffect } from "react";

import { Button } from "@/components/ui/button";

import type { Episode } from "../episodes/useEpisodes";
import { Workstation } from "../episodes/Workstation";
import { LabelPanel } from "./LabelPanel";
import { nextInQueue, QUEUE_LABELS, type LabelQueue } from "./queue";

export function LabelSession(props: {
  episode: Episode;
  queue: LabelQueue;
  remaining: string[]; // the queue's Episodes still to label, this one included
  phrases: string[];
  onOpen: (id: string | null) => void;
}) {
  const { episode, onOpen } = props;
  const next = nextInQueue(props.remaining, episode.id);
  const position = props.remaining.indexOf(episode.id);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !document.querySelector("[role=dialog]")) onOpen(null);
    };
    globalThis.addEventListener("keydown", onKey);
    return () => {
      globalThis.removeEventListener("keydown", onKey);
    };
  }, [onOpen]);

  return (
    <div className="p-6">
      <div className="mb-3 flex items-center gap-2 text-sm">
        <nav aria-label="Breadcrumb" className="flex items-center gap-1.5">
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground"
            onClick={() => {
              onOpen(null);
            }}
          >
            Reference labels
          </button>
          <span className="text-muted-foreground">/</span>
          <span className="text-muted-foreground">{QUEUE_LABELS[props.queue]}</span>
          <span className="text-muted-foreground">/</span>
          <span className="font-medium">{episode.id}</span>
        </nav>
        <span className="ml-auto text-xs text-muted-foreground tabular-nums">
          {position >= 0 ? `${String(position + 1)} of ${String(props.remaining.length)} left` : ""}
          {" · Esc back"}
        </span>
        <Button
          size="sm"
          variant="ghost"
          disabled={!next}
          onClick={() => {
            onOpen(next);
          }}
        >
          Skip
        </Button>
      </div>
      <Workstation
        episode={episode}
        blind
        actions={(playhead) => (
          <LabelPanel
            episode={episode}
            phrases={props.phrases}
            playhead={playhead}
            relabel={props.queue === "relabel"}
            onSaved={() => {
              onOpen(next);
            }}
          />
        )}
      />
    </div>
  );
}
