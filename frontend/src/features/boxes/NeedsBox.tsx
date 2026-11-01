// Prepare's queue of Episodes with no hand-drawn box: a frame-0 grid and the box dialog.
import { useState } from "react";

import { Button } from "@/components/ui/button";

import { SectionHeading } from "../core/PageHeader";
import type { Episode } from "../episodes/useEpisodes";
import { BoxDialog } from "./BoxDialog";
import { frame0Url, useBoxes } from "./useBoxes";

export function NeedsBox(props: { episodes: Episode[] }) {
  const boxes = useBoxes();
  const [queue, setQueue] = useState<Episode[] | null>(null);
  const boxed = new Set(boxes.data?.map((b) => b.episode_id));
  const missing = props.episodes.filter((e) => !boxed.has(e.id) && e.cameras.length > 0);
  const startAt = (index: number) => {
    setQueue([...missing.slice(index), ...missing.slice(0, index)]);
  };

  return (
    <section className="mt-8">
      <SectionHeading
        title="Needs a box"
        meta={`${String(missing.length)} Episodes`}
        info="One box per Episode, around the task object on frame 0. It seeds the exterior track that placement Criteria read; without one, they come back unsure and nothing blocks."
        actions={
          <Button
            size="sm"
            disabled={missing.length === 0}
            onClick={() => {
              startAt(0);
            }}
          >
            Draw boxes ({missing.length})
          </Button>
        }
      />
      <div className="mt-4 grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-3">
        {missing.map((episode, index) => (
          <button
            key={episode.id}
            type="button"
            className="group text-left"
            aria-label={`Draw a box for Episode ${String(episode.index)}`}
            onClick={() => {
              startAt(index);
            }}
          >
            <img
              src={frame0Url(episode.id, "exterior_image_1_left")}
              alt=""
              loading="lazy"
              className="aspect-video w-full rounded border bg-muted object-cover group-hover:ring-2 group-hover:ring-primary"
            />
            <div className="mt-1 text-xs font-medium">Episode {episode.index}</div>
            <div className="truncate text-xs text-muted-foreground">
              {episode.instruction ?? "No instruction"}
            </div>
          </button>
        ))}
        {missing.length === 0 && props.episodes.length > 0 && (
          <p className="text-sm text-muted-foreground">Every Episode has its box.</p>
        )}
      </div>
      {queue && (
        <BoxDialog
          queue={queue}
          onClose={() => {
            setQueue(null);
          }}
        />
      )}
    </section>
  );
}
