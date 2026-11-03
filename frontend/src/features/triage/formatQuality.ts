/** An Episode's quality, signed, so above and below the run's typical Episode read at a glance. */
export function formatQuality(quality: number): string {
  const shown = Math.abs(quality).toFixed(2);
  if (shown === "0.00") return shown;
  return `${quality > 0 ? "+" : "−"}${shown}`;
}
