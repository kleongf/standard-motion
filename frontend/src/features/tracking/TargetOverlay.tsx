// The Episode's target box over the video, on the boxed exterior view only. A fixed place, so
// it ignores the playhead. Hidden while blind.
import { useTargetBox } from "./useTargetBoxes";

export function TargetOverlay(props: {
  episodeId: string;
  camera: string;
  hidden?: boolean | undefined;
}) {
  const target = useTargetBox(props.episodeId, props.hidden);
  const box = target?.camera === props.camera ? target.box : null;
  if (!target || !box) return null;
  const percent = (value: number, of: number) => `${String((value / of) * 100)}%`;
  return (
    <div
      data-testid="target-box"
      aria-label="Target box"
      className="pointer-events-none absolute rounded-sm border-2 border-dashed border-emerald-400 bg-emerald-400/10 shadow-[0_0_0_1px_rgba(0,0,0,0.5)]"
      style={{
        left: percent(box.left, target.frame_width),
        top: percent(box.top, target.frame_height),
        width: percent(box.right - box.left, target.frame_width),
        height: percent(box.bottom - box.top, target.frame_height),
      }}
    />
  );
}
