// Where clicking a Criterion lane takes the Workstation: the moment it went wrong (or its first
// moment, or its window's start) on the view that decides it.
import type { CriterionResult } from "./useTriage";

export interface LaneFocus {
  t: number;
  /** The camera to switch to; null keeps the current one (robot data has no view). */
  camera: string | null;
}

export function laneFocus(result: CriterionResult, cameras: string[]): LaneFocus {
  const t = result.at_s ?? result.moments[0]?.t ?? result.window?.start ?? 0;
  const camera = result.camera && cameras.includes(result.camera) ? result.camera : null;
  return { t, camera };
}

/** A time's position along a lane as a CSS percentage, clamped to the Episode. */
export function lanePercent(t: number, duration: number): string {
  if (duration <= 0) return "0%";
  return `${String(Math.max(0, Math.min(100, (t / duration) * 100)))}%`;
}
