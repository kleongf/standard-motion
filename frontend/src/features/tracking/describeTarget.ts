import type { Rect } from "../boxes/boxFromDrag";
import type { TargetBox } from "./useTargetBoxes";

/** Who found the target box, or why there is none yet (`missing`: it needs drawing). */
export function describeTarget(target: TargetBox): { text: string; missing: boolean } {
  const words = `“${target.target ?? ""}”`;
  switch (target.status) {
    case "found":
      return {
        text: target.origin === "hand" ? "Hand-drawn" : `SAM found ${words}`,
        missing: false,
      };
    case "not_found":
      return { text: `SAM found no ${words}`, missing: true };
    case "no_instruction":
      return { text: "No instruction to prompt SAM with", missing: true };
    case "no_target":
      return { text: "The instruction names no target", missing: true };
  }
}

/** The target box in whole frame pixels, as the box canvas draws it. */
export function targetRect(target: TargetBox): Rect | null {
  const { box } = target;
  if (!box) return null;
  return {
    x1: Math.round(box.left),
    y1: Math.round(box.top),
    x2: Math.round(box.right),
    y2: Math.round(box.bottom),
  };
}
