import { describe, expect, it } from "vitest";

import {
  balancedAccuracyText,
  countOf,
  interval,
  lengthRuleText,
  minutesText,
  slackText,
  usdText,
} from "./reportText";

describe("report text", () => {
  it("puts the count first and the interval separately, never ±", () => {
    const p = { count: 1, of: 2, low: 0.0945, high: 0.9055 };
    expect(countOf(p)).toBe("1 of 2");
    expect(interval(p)).toBe("0.09–0.91");
  });

  it("has no interval when there is nothing to count", () => {
    expect(interval({ count: 0, of: 0, low: null, high: null })).toBeNull();
  });

  it("states Length alone's hindsight threshold and side", () => {
    expect(lengthRuleText({ keep: "shorter", threshold_s: 12.4 })).toBe(
      "Length alone keeps Episodes ≤ 12.4 s (threshold set in hindsight).",
    );
    expect(lengthRuleText(null)).toMatch(/no labelled Episode/);
  });

  it("says where the slack comes from, or that there is none yet", () => {
    expect(slackText({ seconds: 0.95, edges: 2, episodes: 1 })).toBe(
      "Slack 0.95 s: the 95th percentile of 2 interval edges over 1 relabelled Episode.",
    );
    expect(slackText({ seconds: null, edges: 0, episodes: 0 })).toBe(
      "No slack yet: no Phrase has failed in both a first pass and its relabel.",
    );
  });

  it("shows balanced accuracy to two places, or a dash when it can't be scored", () => {
    expect(balancedAccuracyText((2 / 3 + 1 / 2) / 2)).toBe("0.58");
    expect(balancedAccuracyText(null)).toBe("–");
  });

  it("prices in dollars, with more places for sums under a cent", () => {
    expect(usdText(8.2)).toBe("$8.20");
    expect(usdText(0.0514)).toBe("$0.05");
    expect(usdText(0.0028)).toBe("$0.0028");
    expect(usdText(0)).toBe("$0.00");
    expect(usdText(null)).toBe("–");
  });

  it("states minutes to one place", () => {
    expect(minutesText(1.5)).toBe("1.5 min");
    expect(minutesText(null)).toBe("–");
  });
});
