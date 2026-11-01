import { expect, test } from "vitest";

import { recompileNote } from "./recompileNote";

// "Tidy pick: one grasp only, and pauses are fine."
const phrases = [
  { start: 0, end: 9 },
  { start: 11, end: 25 },
  { start: 31, end: 46 },
];

test("says nothing after a compile of the whole Description", () => {
  expect(recompileNote(null, phrases)).toBeNull();
});

test("names the changed text and counts the Phrases kept", () => {
  const changed = [{ start: 31, end: 46, text: "pauses are fine" }];

  expect(recompileNote(changed, phrases)).toBe(
    "Recompiled only “pauses are fine”; kept 2 unchanged Phrases with their Criteria and labels.",
  );
});

test("joins several changes, and says when an edit only took text out", () => {
  const changed = [
    { start: 0, end: 9, text: "Tidy pick" },
    { start: 31, end: 46, text: "pauses are fine" },
  ];

  expect(recompileNote(changed, phrases)).toBe(
    "Recompiled only “Tidy pick” and “pauses are fine”; kept 1 unchanged Phrase with its Criteria and labels.",
  );
  expect(recompileNote([], phrases)).toBe(
    "Nothing new to compile; kept 3 unchanged Phrases with their Criteria and labels.",
  );
});
