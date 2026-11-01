// Frame 0 of the boxed view with the object box (sky) and the target box (emerald) on it.
import type { Box } from "../boxes/useBoxes";
import type { TargetBox } from "./useTargetBoxes";

export function FrameBoxes(props: { src: string; box: Box; target: TargetBox | undefined }) {
  const { box } = props;
  const target = props.target?.box;
  return (
    <div className="relative aspect-video w-full overflow-hidden rounded border bg-muted">
      <img src={props.src} alt="" loading="lazy" className="absolute inset-0 h-full w-full" />
      <svg
        viewBox={`0 0 ${String(box.frame_width)} ${String(box.frame_height)}`}
        className="pointer-events-none absolute inset-0 h-full w-full"
      >
        <rect
          aria-label="Object box"
          x={box.x1}
          y={box.y1}
          width={box.x2 - box.x1}
          height={box.y2 - box.y1}
          fill="none"
          stroke="#38bdf8"
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
        />
        {target && (
          <rect
            aria-label="Target box"
            x={target.left}
            y={target.top}
            width={target.right - target.left}
            height={target.bottom - target.top}
            fill="rgba(52,211,153,0.15)"
            stroke="#34d399"
            strokeWidth={2}
            strokeDasharray="4 2"
            vectorEffect="non-scaling-stroke"
          />
        )}
      </svg>
    </div>
  );
}
