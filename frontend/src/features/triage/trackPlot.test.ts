import { describe, expect, it } from "vitest";

import { plotDomain, plotRuns, plotValueAt } from "./trackPlot";
import type { TrackPlot } from "./useTriage";

const PLOT: TrackPlot = {
  label: "Object from the fingers",
  unit: "box-widths",
  level: 1.5,
  points: [
    { t: 1.0, value: 0.1 },
    { t: 1.2, value: 0.3 },
    { t: 1.4, value: null },
    { t: 1.6, value: 2.0 },
    { t: 1.8, value: 2.5 },
  ],
};

describe("plotRuns", () => {
  it("breaks the line where SAM had no box", () => {
    expect(plotRuns(PLOT.points).map((run) => run.map((p) => p.t))).toEqual([
      [1.0, 1.2],
      [1.6, 1.8],
    ]);
  });
});

describe("plotValueAt", () => {
  it("reads the 5 fps frame showing at the time, or nothing outside the plot or without a box", () => {
    expect(plotValueAt(PLOT, 1.29)).toBe(0.3);
    expect(plotValueAt(PLOT, 1.5)).toBeNull();
    expect(plotValueAt(PLOT, 1.95)).toBe(2.5);
    expect(plotValueAt(PLOT, 0.5)).toBeNull();
    expect(plotValueAt(PLOT, 2.5)).toBeNull();
  });
});

describe("plotDomain", () => {
  it("spans zero, the values and the level, with a little room", () => {
    const [lo, hi] = plotDomain(PLOT);
    expect(lo).toBeLessThan(0);
    expect(hi).toBeGreaterThan(2.5);
    const [emptyLo, emptyHi] = plotDomain({ ...PLOT, points: [] });
    expect(emptyLo).toBeCloseTo(-0.15);
    expect(emptyHi).toBeCloseTo(1.65);
  });
});
