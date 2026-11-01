import { expect, test } from "vitest";

import { descriptionSegments } from "./descriptionSegments";

const DESCRIPTION = "Tidy pick: one grasp only, and no long pauses.";

test("splits the Description into Phrases, uncovered words and the text between", () => {
  const phrases = [{ start: 11, end: 25 }];
  const uncovered = [
    { start: 0, end: 4 },
    { start: 5, end: 9 },
    { start: 31, end: 33 },
    { start: 34, end: 38 },
    { start: 39, end: 45 },
  ];

  expect(descriptionSegments(DESCRIPTION, phrases, uncovered)).toEqual([
    { text: "Tidy", uncovered: true },
    { text: " " },
    { text: "pick", uncovered: true },
    { text: ": " },
    { text: "one grasp only", phrase: 0 },
    { text: ", and " },
    { text: "no", uncovered: true },
    { text: " " },
    { text: "long", uncovered: true },
    { text: " " },
    { text: "pauses", uncovered: true },
    { text: "." },
  ]);
});

test("Phrases keep their index whatever order they come in", () => {
  const phrases = [
    { start: 31, end: 45 },
    { start: 0, end: 9 },
  ];

  expect(descriptionSegments(DESCRIPTION, phrases, [])).toEqual([
    { text: "Tidy pick", phrase: 1 },
    { text: ": one grasp only, and " },
    { text: "no long pauses", phrase: 0 },
    { text: "." },
  ]);
});
