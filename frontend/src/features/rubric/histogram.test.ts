import { describe, expect, it } from "vitest";

import { binValues, formatValue, roundThreshold, sliderDomain } from "./histogram";

describe("sliderDomain", () => {
  it("steps whole counts and spans every value, the threshold and one more", () => {
    expect(sliderDomain([1, 1, 3], 1, 0, "attempts")).toEqual({ min: 0, max: 4, step: 1 });
  });

  it("pads measured values and keeps the margin band in range", () => {
    const domain = sliderDomain([0.4, 1.2], 2, 0.2, "s");
    expect(domain.min).toBe(0);
    expect(domain.max).toBeGreaterThan(2.2);
    expect(domain.step).toBeCloseTo(domain.max / 100);
  });

  it("has a range even when every value sits on the threshold", () => {
    const domain = sliderDomain([0, 0], 0, 0, "s");
    expect(domain.max).toBeGreaterThan(domain.min);
  });
});

describe("binValues", () => {
  it("stacks each bin by status and leaves out what couldn't be measured", () => {
    const domain = { min: 0, max: 4, step: 1 };
    const bins = binValues(
      [
        { value: 1, status: "pass" },
        { value: 1, status: "pass" },
        { value: 3, status: "fail" },
        { value: null, status: "unsure" },
      ],
      domain,
    );
    expect(bins).toHaveLength(5); // one per whole count, 0 to 4
    expect(bins[1]).toMatchObject({ pass: 2, fail: 0, unsure: 0 });
    expect(bins[3]).toMatchObject({ pass: 0, fail: 1, unsure: 0 });
    expect(bins.reduce((n, b) => n + b.pass + b.fail + b.unsure, 0)).toBe(3);
  });

  it("puts a value at the top of the range in the last bin", () => {
    const bins = binValues([{ value: 2, status: "unsure" }], { min: 0, max: 2, step: 0.02 }, 10);
    expect(bins).toHaveLength(10);
    expect(bins[9]?.unsure).toBe(1);
  });
});

describe("roundThreshold", () => {
  it("keeps a dragged threshold to what its unit can tell apart", () => {
    expect(roundThreshold(1.23456, "s")).toBe(1.23);
    expect(roundThreshold(0.05349, "m")).toBe(0.053);
    expect(roundThreshold(2.4, "attempts")).toBe(2);
  });
});

describe("formatValue", () => {
  it("reads metres as centimetres and counts as whole numbers", () => {
    expect(formatValue(0.053, "m")).toBe("5.3 cm");
    expect(formatValue(2, "attempts")).toBe("2");
    expect(formatValue(1.25, "s")).toBe("1.25 s");
    expect(formatValue(0.6, "ratio")).toBe("0.60");
  });
});
