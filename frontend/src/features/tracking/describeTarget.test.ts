import { expect, test } from "vitest";

import { describeTarget, targetRect } from "./describeTarget";
import type { TargetBox } from "./useTargetBoxes";

function target(overrides: Partial<TargetBox> = {}): TargetBox {
  return {
    episode_id: "droid_100:0",
    camera: "exterior_image_2_left",
    origin: "sam",
    status: "found",
    target: "grey bowl",
    box: { left: 10.4, top: 20, right: 60.6, bottom: 80 },
    frame_width: 320,
    frame_height: 180,
    made_at: "2026-10-29T10:00:00+00:00",
    ...overrides,
  };
}

test("says who found the target box, or why there is none", () => {
  expect(describeTarget(target())).toEqual({ text: "SAM found “grey bowl”", missing: false });
  expect(describeTarget(target({ origin: "hand" }))).toEqual({
    text: "Hand-drawn",
    missing: false,
  });
  expect(describeTarget(target({ status: "not_found", box: null }))).toEqual({
    text: "SAM found no “grey bowl”",
    missing: true,
  });
  expect(describeTarget(target({ status: "no_instruction", target: null, box: null }))).toEqual({
    text: "No instruction to prompt SAM with",
    missing: true,
  });
  expect(describeTarget(target({ status: "no_target", target: null, box: null }))).toEqual({
    text: "The instruction names no target",
    missing: true,
  });
});

test("a target box becomes whole frame pixels to start a redraw from", () => {
  expect(targetRect(target())).toEqual({ x1: 10, y1: 20, x2: 61, y2: 80 });
  expect(targetRect(target({ box: null }))).toBeNull();
});
