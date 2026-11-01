import { describe, expect, it } from "vitest";

import { formatQuality } from "./formatQuality";

describe("formatQuality", () => {
  it("signs a quality above or below the run's typical Episode", () => {
    expect(formatQuality(0.674)).toBe("+0.67");
    expect(formatQuality(-1.349)).toBe("−1.35");
    expect(formatQuality(0)).toBe("0.00");
    expect(formatQuality(-0.001)).toBe("0.00");
  });
});
