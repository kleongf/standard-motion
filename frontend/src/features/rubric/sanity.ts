// The Rubric sanity monitor's words: a hard Criterion's fail rate over the anchor pool, with its
// Wilson interval, and what a warning on it means. The numbers come from the backend.
import type { components } from "../../api/schema";
import type { AnchorPreview } from "./useDraftEdits";

type Proportion = components["schemas"]["Proportion"];
type SanityWarning = NonNullable<components["schemas"]["CriterionPreview"]["warning"]>;

function percent(fraction: number): string {
  const rounded = Math.round(fraction * 1000) / 10;
  return `${String(rounded)}%`;
}

/** "0 of 5 fail · 0% (95% interval 0%–43.4%)". */
export function failRateLine(rate: Proportion): string {
  const counts = `${String(rate.count)} of ${String(rate.of)} fail`;
  if (rate.of === 0 || rate.low === null || rate.high === null) return counts;
  return `${counts} · ${percent(rate.count / rate.of)} (95% interval ${percent(rate.low)}–${percent(rate.high)})`;
}

export const WARNING_CHIPS: Record<SanityWarning, string> = {
  too_rare: "Rarely fails",
  too_common: "Nearly always fails",
};

export const WARNING_EXPLAINED: Record<SanityWarning, string> = {
  too_rare: "Under 2% of the anchor pool fails this: it may reject almost nothing.",
  too_common: "Over 95% of the anchor pool fails this: it may reject almost everything.",
};

const BOUNDS: Record<SanityWarning, number> = { too_rare: 0.02, too_common: 0.95 };

/** What a warning means, hedged when the interval still contains its bound: the observed rate
 * crossed it, but this few Episodes can't tell whether the true one does. */
export function warningNote(warning: SanityWarning, rate: Proportion): string {
  const { low, high } = rate;
  const bound = BOUNDS[warning];
  const unsettled = low !== null && high !== null && low <= bound && bound <= high;
  if (!unsettled) return WARNING_EXPLAINED[warning];
  const episodes = `${String(rate.of)} anchor Episode${rate.of === 1 ? "" : "s"}`;
  return `${WARNING_EXPLAINED[warning]} Only ${episodes}: too few to tell.`;
}

export function warningCount(preview: AnchorPreview | undefined): number {
  return preview?.criteria.filter((c) => c.warning).length ?? 0;
}
