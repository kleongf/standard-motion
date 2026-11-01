// The margin multiplier as the Describe page states it: what s is and how many labels tuned it,
// never as a guarantee, and why to label more.
import type { CalibrationRecord } from "./useCalibration";

/** At least one decimal: "1.0", "0.75". */
export function sText(s: number): string {
  return Number.isInteger(s) ? s.toFixed(1) : String(s);
}

/** e.g. "s = 1.0 · tuned on 24 labels". */
export function multiplierLine(s: number, record: CalibrationRecord | null): string {
  if (!record) return `s = ${sText(s)} · not tuned yet`;
  const labels = `${String(record.n_labels)} label${record.n_labels === 1 ? "" : "s"}`;
  return `s = ${sText(s)} · tuned on ${labels}`;
}

export function warnings(
  record: CalibrationRecord | null,
  maxErrorRate: number,
  confidence: number,
): string[] {
  if (!record) return [];
  const found: string[] = [];
  if (!record.bound_met) {
    const at = `${String(Math.round(confidence * 100))}%`;
    found.push(
      `No s kept the errors' upper bound at ${String(maxErrorRate)} or under (${at}), so s stays at the widest, ${sText(record.s)}: label more.`,
    );
  }
  if (record.unstable) found.push("Margins unstable: label more. Dropping 2 labels moves s.");
  return found;
}
