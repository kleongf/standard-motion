/** An Episode's quality, signed, so above and below the run's typical Episode read at a glance. */
export function formatQuality(quality: number): string {
  const shown = Math.abs(quality).toFixed(2);
  if (shown === "0.00") return shown;
  return `${quality > 0 ? "+" : "−"}${shown}`;
}

export const QUALITY_TITLE =
  "Quality: how this Episode's soft Criteria rank it in the run, in robust standard deviations " +
  "from the typical Episode (0). Higher is better; it never decides.";
