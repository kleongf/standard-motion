// What the last compile did, when it recompiled only an edit: which changed text Spark was asked
// about, and how many Phrases it kept as they were.
import type { components } from "../../api/schema";
import type { Span } from "./descriptionSegments";

type TextRange = components["schemas"]["TextRange"];

function plural(n: number, word: string): string {
  return `${String(n)} ${word}${n === 1 ? "" : "s"}`;
}

function quoted(texts: string[]): string {
  const marks = texts.map((t) => `“${t}”`);
  return marks.length > 1
    ? `${marks.slice(0, -1).join(", ")} and ${marks.at(-1) ?? ""}`
    : marks.join("");
}

/** Null after a compile of the whole Description. */
export function recompileNote(
  recompiled: readonly TextRange[] | null | undefined,
  phrases: readonly Span[],
): string | null {
  if (!recompiled) return null;
  const overlaps = (p: Span) => recompiled.some((c) => p.start < c.end && c.start < p.end);
  const n = phrases.filter((p) => !overlaps(p)).length;
  const kept = `kept ${plural(n, "unchanged Phrase")} with ${n === 1 ? "its" : "their"} Criteria and labels`;
  if (recompiled.length === 0) return `Nothing new to compile; ${kept}.`;
  return `Recompiled only ${quoted(recompiled.map((c) => c.text))}; ${kept}.`;
}
