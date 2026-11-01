import { expect, test } from "vitest";

import { draftProblem, emptyDraft, toPhraseLabels, type Judgment } from "./labelDraft";

const PHRASES = ["grasps the object on the first try", "never drops it"];
const pass: Judgment = { passed: true, start: null, end: null };

test("nothing can be saved until every Phrase is judged", () => {
  expect(draftProblem(PHRASES, emptyDraft(2), null)).toBe(
    "Judge “grasps the object on the first try”",
  );
  expect(draftProblem(PHRASES, [pass, pass], null)).toBeNull();
});

test("a fail can't be saved without its start and end", () => {
  const failing = (start: number | null, end: number | null): Judgment[] => [
    pass,
    { passed: false, start, end },
  ];
  expect(draftProblem(PHRASES, failing(null, null), null)).toBe(
    "Mark where “never drops it” fails: its start and end",
  );
  expect(draftProblem(PHRASES, failing(1.2, null), null)).toBe(
    "Mark where “never drops it” fails: its start and end",
  );
  expect(draftProblem(PHRASES, failing(1.2, 0.4), null)).toBe(
    "“never drops it” ends before it starts",
  );
  expect(draftProblem(PHRASES, failing(0.4, 1.2), null)).toBeNull();
});

test("an Episode with no instruction needs one written", () => {
  expect(draftProblem(PHRASES, [pass, pass], "  ")).toBe("Write the instruction it attempts");
  expect(draftProblem(PHRASES, [pass, pass], "Put the block in the bowl")).toBeNull();
});

test("only a fail carries its interval", () => {
  const judged: Judgment[] = [
    { passed: true, start: 0.2, end: null }, // marked, then switched back to pass
    { passed: false, start: 0.4, end: 1.2 },
  ];
  expect(toPhraseLabels(PHRASES, judged)).toEqual([
    { phrase: PHRASES[0], passed: true, interval: null },
    { phrase: PHRASES[1], passed: false, interval: { start_s: 0.4, end_s: 1.2 } },
  ]);
});
