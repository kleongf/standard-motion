// The anchor-pool histogram under a Criterion's threshold slider: the slider's range, and the
// values binned and stacked by status. Statuses come from the server; nothing here scores.
import type { components } from "../../api/schema";

type AnchorValue = Pick<components["schemas"]["AnchorValue"], "value" | "status">;

export interface Domain {
  min: number;
  max: number;
  step: number;
}

export interface Bin {
  start: number;
  end: number;
  pass: number;
  fail: number;
  unsure: number;
}

const COUNTS = new Set(["attempts"]);
const STEPS = 100;

/** The slider's range: every anchor value, the threshold and its margin band, padded. Counts
 * step by one; other units in hundredths of the range, from 0 unless something is negative. */
export function sliderDomain(
  values: number[],
  threshold: number,
  margin: number,
  unit: string,
): Domain {
  const low = Math.min(threshold - margin, ...values);
  const high = Math.max(threshold + margin, ...values);
  if (COUNTS.has(unit)) {
    return { min: Math.max(0, Math.floor(low) - 1), max: Math.ceil(high) + 1, step: 1 };
  }
  const span = high - low || Math.max(Math.abs(high), 1);
  const fromZero = unit !== "m" && low >= 0; // durations and ratios read best from 0
  const min = fromZero ? 0 : low - span * 0.1;
  const max = high + span * 0.1;
  return { min, max, step: (max - min) / STEPS };
}

/** Counts get a bin per whole number; other units `count` equal bins. */
export function binValues(values: AnchorValue[], domain: Domain, count = 12): Bin[] {
  const whole = domain.step === 1;
  const n = whole ? domain.max - domain.min + 1 : count;
  const width = whole ? 1 : (domain.max - domain.min) / n;
  const bins: Bin[] = Array.from({ length: n }, (_, i) => ({
    start: domain.min + i * width - (whole ? 0.5 : 0),
    end: domain.min + (i + 1) * width - (whole ? 0.5 : 0),
    pass: 0,
    fail: 0,
    unsure: 0,
  }));
  for (const { value, status } of values) {
    if (value === null) continue;
    const at = whole ? Math.round(value - domain.min) : Math.floor((value - domain.min) / width);
    const bin = bins[Math.min(n - 1, Math.max(0, at))];
    if (bin) bin[status] += 1;
  }
  return bins;
}

/** A dragged threshold, kept to what its unit can tell apart: whole counts, millimetres,
 * hundredths otherwise. */
export function roundThreshold(value: number, unit: string): number {
  if (COUNTS.has(unit)) return Math.round(value);
  const places = unit === "m" ? 1000 : 100;
  return Math.round(value * places) / places;
}

/** A value as the Criterion's English reads it. */
export function formatValue(value: number, unit: string): string {
  if (unit === "attempts") return String(Math.round(value));
  if (unit === "m") return `${String(Math.round(value * 1000) / 10)} cm`;
  if (unit === "ratio") return value.toFixed(2);
  return `${String(Math.round(value * 100) / 100)} ${unit}`;
}
