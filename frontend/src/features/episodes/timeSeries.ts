// What a TimePlot draws from: points in time, and the value range to fit them in.

export interface TimePoint {
  t: number;
  value: number;
}

/** The range from `lo` to `hi`, padded by a tenth (or by `minPad` when they're equal). */
export function padded(lo: number, hi: number, minPad: number): [number, number] {
  const pad = (hi - lo) * 0.1 || minPad;
  return [lo - pad, hi + pad];
}
