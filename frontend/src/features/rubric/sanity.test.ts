import { describe, expect, it } from "vitest";

import type { AnchorPreview } from "./useDraftEdits";
import { failRateLine, warningCount, warningNote } from "./sanity";

describe("failRateLine", () => {
  it("reads the count, the rate and the Wilson interval", () => {
    const line = failRateLine({ count: 1, of: 20, low: 0.0089, high: 0.2361 });
    expect(line).toBe("1 of 20 fail · 5% (95% interval 0.9%–23.6%)");
  });

  it("has no interval for an empty pool", () => {
    expect(failRateLine({ count: 0, of: 0, low: null, high: null })).toBe("0 of 0 fail");
  });
});

describe("warningNote", () => {
  it("hedges when the interval still contains 2%", () => {
    const note = warningNote("too_rare", { count: 0, of: 1, low: 0, high: 0.793 });
    expect(note).toBe(
      "Under 2% of the anchor pool fails this: it may reject almost nothing. " +
        "Only 1 anchor Episode: too few to tell.",
    );
  });

  it("hedges when the interval still contains 95%", () => {
    const note = warningNote("too_common", { count: 4, of: 4, low: 0.51, high: 1 });
    expect(note).toContain("Only 4 anchor Episodes: too few to tell.");
  });

  it("states the warning plainly once the interval clears the bound", () => {
    const rare = warningNote("too_rare", { count: 0, of: 400, low: 0, high: 0.0095 });
    const common = warningNote("too_common", { count: 400, of: 400, low: 0.9905, high: 1 });
    expect(rare).toBe("Under 2% of the anchor pool fails this: it may reject almost nothing.");
    expect(common).toBe("Over 95% of the anchor pool fails this: it may reject almost everything.");
  });
});

describe("warningCount", () => {
  const criterion = (warning: "too_rare" | null) =>
    ({ warning }) as AnchorPreview["criteria"][number];

  it("counts the Criteria with a warning", () => {
    const preview = {
      criteria: [criterion("too_rare"), criterion(null), criterion("too_rare")],
    } as AnchorPreview;
    expect(warningCount(preview)).toBe(2);
  });

  it("is 0 with no preview", () => {
    expect(warningCount(undefined)).toBe(0);
  });
});
