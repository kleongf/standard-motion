import { describe, expect, it } from "vitest";

import { laneFocus, lanePercent } from "./laneFocus";
import type { CriterionResult } from "./useTriage";

function result(overrides: Partial<CriterionResult>): CriterionResult {
  return {
    criterion_id: "grasp-attempts",
    phrase: "grasps the object on the first try",
    primitive: "grasp_attempts",
    kind: "measured",
    hard: true,
    english: "Grasp attempts, up to and including the grasp, ≤ 1",
    status: "fail",
    value: 3,
    measurement: "3 attempts",
    comparator: "<=",
    threshold: 1,
    unit: "attempts",
    evidence: [],
    moments: [
      { t: 0.9, label: "Attempt 1" },
      { t: 1.8, label: "Grasp" },
    ],
    window: { start: 0, end: 3 },
    window_name: "whole Episode",
    at_s: 0.9,
    uncertainty: null,
    margin: 0,
    p_pass: 0,
    camera: null,
    track_plot: null,
    ...overrides,
  };
}

const CAMERAS = ["exterior_image_1_left", "wrist_image_left"];

describe("laneFocus", () => {
  it("seeks a fail to where it went wrong and keeps the camera for robot data", () => {
    expect(laneFocus(result({ at_s: 1.3 }), CAMERAS)).toEqual({ t: 1.3, camera: null });
  });

  it("seeks a pass to its first moment", () => {
    expect(laneFocus(result({ status: "pass", at_s: null }), CAMERAS).t).toBe(0.9);
  });

  it("falls back to the window's start, then to 0", () => {
    expect(
      laneFocus(result({ at_s: null, moments: [], window: { start: 2, end: 3 } }), CAMERAS).t,
    ).toBe(2);
    expect(laneFocus(result({ at_s: null, moments: [], window: null }), CAMERAS).t).toBe(0);
  });

  it("switches to the result's camera when the Episode has that clip", () => {
    expect(laneFocus(result({ camera: "wrist_image_left" }), CAMERAS).camera).toBe(
      "wrist_image_left",
    );
    expect(laneFocus(result({ camera: "exterior_image_2_left" }), CAMERAS).camera).toBeNull();
  });
});

describe("lanePercent", () => {
  it("places a time along the lane, clamped to it", () => {
    expect(lanePercent(1.5, 3)).toBe("50%");
    expect(lanePercent(4, 3)).toBe("100%");
    expect(lanePercent(1, 0)).toBe("0%");
  });
});
