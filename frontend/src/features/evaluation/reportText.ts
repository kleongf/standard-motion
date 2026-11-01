// The report's wording, shared with `winnow eval`: counts first, then 95% intervals, never "±".
import type { LengthRule, Proportion, Slack } from "./useEvaluation";

/** e.g. "1 of 4". */
export function countOf(p: Proportion): string {
  return `${String(p.count)} of ${String(p.of)}`;
}

/** e.g. "0.05–0.70"; null when there is nothing to count. */
export function interval(p: Proportion): string | null {
  if (p.low === null || p.high === null) return null;
  return `${p.low.toFixed(2)}–${p.high.toFixed(2)}`;
}

function plural(n: number, noun: string): string {
  return `${String(n)} ${noun}${n === 1 ? "" : "s"}`;
}

export function slackText(slack: Slack): string {
  if (slack.seconds === null) {
    return "No slack yet: no Phrase has failed in both a first pass and its relabel.";
  }
  return (
    `Slack ${slack.seconds.toFixed(2)} s: the 95th percentile of ` +
    `${plural(slack.edges, "interval edge")} over ${plural(slack.episodes, "relabelled Episode")}.`
  );
}

export function balancedAccuracyText(value: number | null): string {
  return value === null ? "–" : value.toFixed(2);
}

export function lengthRuleText(rule: LengthRule | null): string {
  if (rule === null) return "Length alone: no labelled Episode to fit a threshold to.";
  const side = rule.keep === "longer" ? "≥" : "≤";
  return `Length alone keeps Episodes ${side} ${rule.threshold_s.toFixed(1)} s (threshold set in hindsight).`;
}

/** Dollars to the cent, or to four places for a sum under a cent; a dash when there is none. */
export function usdText(usd: number | null): string {
  if (usd === null) return "–";
  return `$${usd > 0 && usd < 0.01 ? usd.toFixed(4) : usd.toFixed(2)}`;
}

export function minutesText(minutes: number | null): string {
  return minutes === null ? "–" : `${minutes.toFixed(1)} min`;
}
