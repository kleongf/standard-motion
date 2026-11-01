// The Workstation panel's line per track: how much of the clip SAM followed, or why there is
// no track, and any sign it lost the object.
import { lossReasons } from "./trackBoxes";
import type { Track } from "./useTracks";

export const KIND_LABELS: Record<string, string> = {
  wrist: "Wrist track",
  exterior: "Exterior track",
};

export function TrackStatus(props: { track: Track }) {
  const { track } = props;
  const reasons = lossReasons(track);
  return (
    <>
      <dt className="text-muted-foreground">{KIND_LABELS[track.kind] ?? track.kind}</dt>
      <dd data-testid={`track-status-${track.kind}`}>
        {track.status === "no_closure" ? (
          <span className="text-muted-foreground">none: the gripper never closed</span>
        ) : (
          <>
            box on {track.boxes.length} of {track.frames} frames
            {reasons.length > 0 && (
              <span className="block text-amber-700 dark:text-amber-400">
                May have lost the object: {reasons.join("; ")}
              </span>
            )}
          </>
        )}
      </dd>
    </>
  );
}
