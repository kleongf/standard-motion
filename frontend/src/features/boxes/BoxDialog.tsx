// Save & next through Episodes that need a box: 1/2 pick the exterior view, Enter saves. The
// view's whole clip loops beside frame 0, so the moved object is easy to recognise.
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";

import { clipUrl, type Episode } from "../episodes/useEpisodes";
import { BoxCanvas } from "./BoxCanvas";
import type { Rect } from "./boxFromDrag";
import { frame0Url, useSaveBox, type ExteriorCamera } from "./useBoxes";

const VIEWS: { camera: ExteriorCamera; label: string; key: string }[] = [
  { camera: "exterior_image_1_left", label: "Exterior 1", key: "1" },
  { camera: "exterior_image_2_left", label: "Exterior 2", key: "2" },
];

export function BoxDialog(props: { queue: Episode[]; onClose: () => void }) {
  const { queue, onClose } = props;
  const [position, setPosition] = useState(0);
  const [camera, setCamera] = useState<ExteriorCamera>("exterior_image_1_left");
  const [box, setBox] = useState<Rect | null>(null);
  const save = useSaveBox();
  const episode = queue[position];

  const advance = () => {
    setBox(null);
    save.reset();
    if (position + 1 >= queue.length) onClose();
    else setPosition(position + 1);
  };
  const pick = (next: ExteriorCamera) => {
    setCamera(next);
    setBox(null); // a box belongs to the frame it was drawn on
  };
  const saveAndNext = () => {
    if (!episode || !box || save.isPending) return;
    save.mutate({ episodeId: episode.id, draw: { camera, ...box } }, { onSuccess: advance });
  };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const view = VIEWS.find((v) => v.key === event.key);
      if (view) pick(view.camera);
      if (event.key === "Enter") {
        event.preventDefault(); // never also "click" whichever button has focus
        saveAndNext();
      }
    };
    globalThis.addEventListener("keydown", onKey);
    return () => {
      globalThis.removeEventListener("keydown", onKey);
    };
  });

  if (!episode) return null;
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        className="sm:max-w-6xl"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
        }}
      >
        <DialogHeader>
          <DialogTitle>
            Episode {episode.index} · box {position + 1} of {queue.length}
          </DialogTitle>
          <DialogDescription>
            {episode.instruction ? `“${episode.instruction}”: ` : ""}drag a box around the object
            being moved, in the view where it looks biggest.
          </DialogDescription>
          {episode.task_object && (
            <p className="text-sm">
              <span className="font-medium">Object:</span> {episode.task_object}
            </p>
          )}
        </DialogHeader>
        <div className="flex items-center gap-1">
          {VIEWS.map((v) => (
            <Button
              key={v.camera}
              size="sm"
              variant={v.camera === camera ? "secondary" : "ghost"}
              aria-pressed={v.camera === camera}
              onClick={() => {
                pick(v.camera);
              }}
            >
              {v.label} ({v.key})
            </Button>
          ))}
          <span className="ml-auto text-xs text-muted-foreground tabular-nums">
            {box
              ? `box ${String(box.x1)}, ${String(box.y1)} → ${String(box.x2)}, ${String(box.y2)} px`
              : "drag on the frame"}
          </span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <figure>
            <BoxCanvas
              key={`${episode.id}-${camera}`}
              src={frame0Url(episode.id, camera)}
              box={box}
              onDraw={setBox}
            />
            <figcaption className="mt-1 text-xs text-muted-foreground">
              Frame 0: draw here
            </figcaption>
          </figure>
          <figure>
            <video
              key={`${episode.id}-${camera}`}
              src={clipUrl(episode.id, camera)}
              aria-label="Episode clip"
              className="aspect-video w-full rounded bg-black"
              autoPlay
              loop
              muted
              playsInline
              controls
            />
            <figcaption className="mt-1 text-xs text-muted-foreground">
              The whole Episode, looping
            </figcaption>
          </figure>
        </div>
        {save.error && (
          <p role="alert" className="text-sm text-destructive">
            {save.error.message}
          </p>
        )}
        <div className="flex items-center gap-2">
          <Progress value={(position / queue.length) * 100} className="h-1 flex-1" />
          <Button variant="ghost" size="sm" onClick={advance}>
            Skip
          </Button>
          <Button size="sm" disabled={!box || save.isPending} onClick={saveAndNext}>
            Save & next ⏎
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
