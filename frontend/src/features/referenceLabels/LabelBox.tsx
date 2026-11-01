// The Episode's hand-drawn exterior box, drawn in the same visit as its label: which view it's
// in, and the box dialog (pick the view, drag on frame 0) to draw or redraw it.
import { useState } from "react";

import { Button } from "@/components/ui/button";

import { BoxDialog } from "../boxes/BoxDialog";
import { useBoxes } from "../boxes/useBoxes";
import type { Episode } from "../episodes/useEpisodes";

const VIEW_LABELS: Record<string, string> = {
  exterior_image_1_left: "Exterior 1",
  exterior_image_2_left: "Exterior 2",
};

export function LabelBox(props: { episode: Episode }) {
  const { episode } = props;
  const [drawing, setDrawing] = useState(false);
  const box = useBoxes().data?.find((b) => b.episode_id === episode.id);
  return (
    <div className="mt-3 flex items-center gap-2 text-xs">
      <span className="font-medium">Box</span>
      <span className="text-muted-foreground" data-testid="label-box">
        {box ? `drawn on ${VIEW_LABELS[box.camera] ?? box.camera}` : "none yet"}
      </span>
      <Button
        size="xs"
        variant="outline"
        className="ml-auto"
        disabled={episode.cameras.length === 0}
        onClick={() => {
          setDrawing(true);
        }}
      >
        {box ? "Redraw box" : "Draw box"}
      </Button>
      {drawing && (
        <BoxDialog
          queue={[episode]}
          onClose={() => {
            setDrawing(false);
          }}
        />
      )}
    </div>
  );
}
