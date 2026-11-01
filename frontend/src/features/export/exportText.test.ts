import { expect, test } from "vitest";

import { exportedOf, testSetText, totalCounts, writesText } from "./exportText";
import type { ExportPreview } from "./useExport";

const SOURCES = [
  { source: "droid_1.0.1", keep: 2, needs_review: 1, reject: 0, awaiting_label: 0, test_set: 1 },
  { source: "droid_100", keep: 1, needs_review: 2, reject: 3, awaiting_label: 2, test_set: 0 },
];

function preview(include: ExportPreview["include"], awaiting = true): ExportPreview {
  const sources = awaiting ? SOURCES : SOURCES.map((s) => ({ ...s, awaiting_label: 0 }));
  const exported = exportedOf(totalCounts(sources), include);
  return { include, rubric_version: 2, sources, exported, nothing_exported: null };
}

test("totals every source's counts, and exports Needs review only when it's included", () => {
  const total = totalCounts(SOURCES);

  expect(total).toEqual({ keep: 3, needs_review: 3, reject: 3, awaiting_label: 2, test_set: 1 });
  expect(exportedOf(total, "keep")).toBe(3);
  expect(exportedOf(total, "keep_and_review")).toBe(6);
});

test("says what an export writes, with the Episodes awaiting a label decided as it runs", () => {
  expect(writesText(preview("keep", false))).toBe("Writes 3 Episodes.");
  expect(writesText(preview("keep"))).toBe(
    "Writes 3 Episodes, plus those of the 2 Episodes awaiting a Reference label that are kept.",
  );
  expect(writesText(preview("keep_and_review"))).toBe(
    "Writes 6 Episodes, plus those of the 2 Episodes awaiting a Reference label that are kept or Needs review.",
  );
  const one = {
    ...preview("keep"),
    sources: [
      { source: "droid_100", keep: 1, needs_review: 0, reject: 0, awaiting_label: 1, test_set: 0 },
    ],
  };
  expect(writesText({ ...one, exported: 1 })).toBe(
    "Writes 1 Episode, plus the 1 Episode awaiting a Reference label if it’s kept.",
  );
});

test("says the Test set is left out, in the singular for one", () => {
  expect(testSetText(1)).toBe(
    "1 Episode in the Test set is left out: the Test set is never exported.",
  );
  expect(testSetText(4)).toBe(
    "4 Episodes in the Test set are left out: the Test set is never exported.",
  );
});
