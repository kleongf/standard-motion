import { describe, expect, it } from "vitest";

import { riskSeries, slackSeries, valueAt } from "./curves";

describe("curves", () => {
  it("plots risk against coverage, covering more Episodes at each point", () => {
    const curve = {
      system: "winnow" as const,
      label: "Winnow",
      episodes: 4,
      points: [
        { confidence: 0.9, covered: 2, errors: 0 },
        { confidence: 0.6, covered: 4, errors: 1 },
      ],
    };
    expect(riskSeries(curve)).toEqual([
      { x: 0.5, y: 0, count: "0 wrong of 2" },
      { x: 1, y: 0.25, count: "1 wrong of 4" },
    ]);
  });

  it("plots right reason as the share of correct Rejects at each slack", () => {
    const row = {
      system: "spark_alone" as const,
      label: "Spark alone",
      at_slack: null,
      curve: [
        { slack_s: 0, right: 1, of: 4 },
        { slack_s: 0.25, right: 3, of: 4 },
      ],
    };
    expect(slackSeries(row)).toEqual([
      { x: 0, y: 0.25, count: "1 of 4" },
      { x: 0.25, y: 0.75, count: "3 of 4" },
    ]);
  });

  it("draws no right-reason line without a correct Reject", () => {
    const row = {
      system: "winnow" as const,
      label: "Winnow",
      at_slack: null,
      curve: [{ slack_s: 0, right: 0, of: 0 }],
    };
    expect(slackSeries(row)).toEqual([]);
  });

  it("reads a series at an x as its last point at or before it", () => {
    const points = [
      { x: 0.25, y: 0, count: "a" },
      { x: 0.75, y: 0.5, count: "b" },
    ];
    expect(valueAt(points, 0.1)).toBeUndefined();
    expect(valueAt(points, 0.5)?.count).toBe("a");
    expect(valueAt(points, 0.75)?.count).toBe("b");
  });
});
