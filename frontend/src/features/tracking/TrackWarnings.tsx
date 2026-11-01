// Short amber pills at the foot of the Workstation panel for what may make a tracked Criterion
// wrong: a track that may have lost the object, or a target box that still needs drawing. The
// detail is on hover and in the panel's Details.
import { TriangleAlert } from "lucide-react";

import { Pill } from "../triage/Pill";
import { describeTarget } from "./describeTarget";
import { lossReasons } from "./trackBoxes";
import { KIND_LABELS } from "./TrackStatus";
import { useTargetBox } from "./useTargetBoxes";
import type { Track } from "./useTracks";

export function TrackWarnings(props: { episodeId: string; tracks: Track[]; hidden: boolean }) {
  const target = useTargetBox(props.episodeId, props.hidden);
  const pills = props.tracks.flatMap((track) => {
    const reasons = lossReasons(track);
    if (reasons.length === 0) return [];
    const name = KIND_LABELS[track.kind] ?? track.kind;
    return [{ text: `${name} may be lost`, title: reasons.join("; ") }];
  });
  if (target) {
    const { text, missing } = describeTarget(target);
    if (missing) pills.push({ text: "No target box", title: text });
  }
  if (pills.length === 0) return null;
  return (
    <div className="mb-2 flex flex-wrap gap-1">
      {pills.map((p) => (
        <Pill key={p.text} tone="warning" title={p.title}>
          <TriangleAlert className="size-3" />
          {p.text}
        </Pill>
      ))}
    </div>
  );
}
