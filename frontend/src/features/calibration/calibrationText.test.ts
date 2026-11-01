import { expect, test } from "vitest";

import { multiplierLine, sText, warnings } from "./calibrationText";
import type { CalibrationRecord } from "./useCalibration";

const record: CalibrationRecord = {
  rubric_version: 2,
  s: 0.75,
  n_labels: 24,
  errors: 2,
  bound_met: true,
  unstable: false,
  created_at: "2026-10-30T00:00:00+00:00",
};

test("writes s with at least one decimal", () => {
  expect([2, 1.5, 1, 0.75, 0.5].map(sText)).toEqual(["2.0", "1.5", "1.0", "0.75", "0.5"]);
});

test("says what s was tuned on, or that it wasn't", () => {
  expect(multiplierLine(1, null)).toBe("s = 1.0 · not tuned yet");
  expect(multiplierLine(0.75, record)).toBe("s = 0.75 · tuned on 24 labels");
  expect(multiplierLine(2, { ...record, s: 2, n_labels: 1 })).toBe("s = 2.0 · tuned on 1 label");
});

test("warns when no s met the bound and when margins are unstable", () => {
  expect(warnings(record, 0.2, 0.9)).toEqual([]);
  expect(warnings({ ...record, s: 2, bound_met: false, unstable: true }, 0.2, 0.9)).toEqual([
    "No s kept the errors' upper bound at 0.2 or under (90%), so s stays at the widest, 2.0: label more.",
    "Margins unstable: label more. Dropping 2 labels moves s.",
  ]);
});
