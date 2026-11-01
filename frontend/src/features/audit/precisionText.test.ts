import { expect, test } from "vitest";

import { goodRejectsText, precisionText } from "./precisionText";

test("states the count, then the Wilson interval", () => {
  expect(
    precisionText({
      good: { count: 14, of: 15, low: 0.702, high: 0.988 },
      lower_bound: null,
      lower_bound_confidence: 0.9,
    }),
  ).toBe("14/15 good · 95% CI 0.70–0.99");
});

test("adds the one-sided bound when every marked Keep is good", () => {
  expect(
    precisionText({
      good: { count: 15, of: 15, low: 0.796, high: 1 },
      lower_bound: 0.858,
      lower_bound_confidence: 0.9,
    }),
  ).toBe("15/15 good · 95% CI 0.80–1.00 · ≥ 0.86 (90%)");
});

test("says so when nothing is marked", () => {
  expect(
    precisionText({
      good: { count: 0, of: 0, low: null, high: null },
      lower_bound: null,
      lower_bound_confidence: 0.9,
    }),
  ).toBe("No Keeps marked yet");
});

test("counts the good Episodes rejected only once a Reject is marked", () => {
  expect(goodRejectsText({ count: 1, of: 3, low: 0.06, high: 0.79 })).toBe(
    "1 of 3 marked Rejects good",
  );
  expect(goodRejectsText({ count: 0, of: 0, low: null, high: null })).toBeNull();
});
