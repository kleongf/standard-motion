// Prepare's target boxes: per boxed Episode, frame 0 of the boxed view with the object box and
// the target box SAM proposed, and a way to draw the target box by hand.
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { SectionHeading } from "../core/PageHeader";
import { frame0Url, useBoxes, type Box } from "../boxes/useBoxes";
import type { Episode } from "../episodes/useEpisodes";
import { FrameBoxes } from "./FrameBoxes";
import { TargetDialog } from "./TargetDialog";
import { describeTarget } from "./describeTarget";
import { useBoxJobProgress } from "./useBoxJobProgress";
import { useTargetBoxes, type TargetBox } from "./useTargetBoxes";

export function TargetBoxes(props: { episodes: Episode[] }) {
  useBoxJobProgress();
  const boxes = useBoxes().data ?? [];
  const targets = new Map(useTargetBoxes().data?.map((t) => [t.episode_id, t]));
  const episodes = new Map(props.episodes.map((e) => [e.id, e]));
  const [drawing, setDrawing] = useState<Box | null>(null);
  const missing = boxes.filter((b) => targets.get(b.episode_id)?.status !== "found").length;
  const drawingEpisode = drawing ? episodes.get(drawing.episode_id) : undefined;

  if (boxes.length === 0) return null;
  return (
    <section className="mt-8">
      <SectionHeading
        title="Target boxes"
        meta={`${String(missing)} without one`}
        info="Where the object should end up, found by SAM from the instruction on frame 0 of the boxed view. Draw it where SAM missed; a drawn box wins."
      />
      <div className="mt-4 grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4">
        {boxes.map((box) => {
          const episode = episodes.get(box.episode_id);
          return episode ? (
            <TargetCard
              key={box.episode_id}
              episode={episode}
              box={box}
              target={targets.get(box.episode_id)}
              onDraw={() => {
                setDrawing(box);
              }}
            />
          ) : null;
        })}
      </div>
      {drawing && drawingEpisode && (
        <TargetDialog
          episode={drawingEpisode}
          box={drawing}
          target={targets.get(drawing.episode_id)}
          onClose={() => {
            setDrawing(null);
          }}
        />
      )}
    </section>
  );
}

function TargetCard(props: {
  episode: Episode;
  box: Box;
  target: TargetBox | undefined;
  onDraw: () => void;
}) {
  const { episode, box, target } = props;
  const described = target ? describeTarget(target) : { text: "Waiting for SAM", missing: false };
  return (
    <div data-testid={`target-card-${episode.id}`}>
      <FrameBoxes src={frame0Url(episode.id, box.camera)} box={box} target={target} />
      <div className="mt-1 flex items-center gap-2">
        <div className="min-w-0 flex-1">
          <div className="text-xs font-medium">Episode {episode.index}</div>
          <div
            data-testid="target-status"
            className={cn(
              "truncate text-xs",
              described.missing ? "text-amber-700 dark:text-amber-400" : "text-muted-foreground",
            )}
          >
            {described.text}
          </div>
        </div>
        <Button
          size="sm"
          variant={described.missing ? "default" : "outline"}
          aria-label={`Draw the target box for Episode ${String(episode.index)}`}
          onClick={props.onDraw}
        >
          {target?.status === "found" ? "Redraw" : "Draw"}
        </Button>
      </div>
    </div>
  );
}
