// The Export page's wording: what each choice includes, the preview's totals, and what an export
// would write.
import type { ExportPreview, Include, SourceCounts } from "./useExport";

export const INCLUDE_LABELS: Record<Include, string> = {
  keep: "Keep only",
  keep_and_review: "Keep + Needs review",
};

export type Counts = Omit<SourceCounts, "source">;

export function totalCounts(sources: SourceCounts[]): Counts {
  const total: Counts = { keep: 0, needs_review: 0, reject: 0, awaiting_label: 0, test_set: 0 };
  for (const s of sources) {
    total.keep += s.keep;
    total.needs_review += s.needs_review;
    total.reject += s.reject;
    total.awaiting_label += s.awaiting_label;
    total.test_set += s.test_set;
  }
  return total;
}

/** The decisions `include` exports. */
export function exportedOf(counts: Counts, include: Include): number {
  return counts.keep + (include === "keep_and_review" ? counts.needs_review : 0);
}

function episodes(n: number): string {
  return `${String(n)} Episode${n === 1 ? "" : "s"}`;
}

/** The warning before exporting Episodes with no Reference label: it warns and never blocks. */
export function unlabelledWarning(unlabelled: number): string {
  if (unlabelled === 1) {
    return "1 Episode isn’t Reference-labelled yet. Exporting shows its decision; label it first if you want it blind.";
  }
  return `${String(unlabelled)} Episodes aren’t Reference-labelled yet. Exporting shows their decisions; label them first if you want them blind.`;
}

/** What pressing Export writes; Episodes awaiting a label are exported by decisions not shown. */
export function writesText(preview: ExportPreview): string {
  const awaiting = totalCounts(preview.sources).awaiting_label;
  const decisions = preview.include === "keep" ? "kept" : "kept or Needs review";
  const writes = `Writes ${episodes(preview.exported)}`;
  if (awaiting === 0) return `${writes}.`;
  return `${writes}, plus those of the ${episodes(awaiting)} awaiting a Reference label that are ${decisions}.`;
}

export function testSetText(testSet: number): string {
  return `${episodes(testSet)} in the Test set ${testSet === 1 ? "is" : "are"} left out: the Test set is never exported.`;
}
