// Draw an Episode's target box by hand, on frame 0 of the view its object was boxed in. It
// starts from SAM's box when there is one; the drawn box replaces it.
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { BoxCanvas } from "../boxes/BoxCanvas";
import type { Rect } from "../boxes/boxFromDrag";
import { frame0Url, type Box } from "../boxes/useBoxes";
import type { Episode } from "../episodes/useEpisodes";
import { targetRect } from "./describeTarget";
import { useDrawTargetBox, type TargetBox } from "./useTargetBoxes";

export function TargetDialog(props: {
  episode: Episode;
  box: Box;
  target: TargetBox | undefined;
  onClose: () => void;
}) {
  const { episode, onClose } = props;
  const [rect, setRect] = useState<Rect | null>(props.target ? targetRect(props.target) : null);
  const [drawn, setDrawn] = useState(false);
  const save = useDrawTargetBox();
  const draw = (next: Rect) => {
    setRect(next);
    setDrawn(true);
  };

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>Episode {episode.index} · target box</DialogTitle>
          <DialogDescription>
            {episode.instruction ? `“${episode.instruction}”: ` : ""}drag a box around where the
            object should end up. It replaces SAM&apos;s.
          </DialogDescription>
        </DialogHeader>
        <BoxCanvas src={frame0Url(episode.id, props.box.camera)} box={rect} onDraw={draw} />
        {save.error && (
          <p role="alert" className="text-sm text-destructive">
            {save.error.message}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            size="sm"
            disabled={!drawn || !rect || save.isPending}
            onClick={() => {
              if (rect) save.mutate({ episodeId: episode.id, rect }, { onSuccess: onClose });
            }}
          >
            Save target box
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
