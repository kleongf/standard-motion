// A Reference label in progress: one judgment per Phrase, each fail with the stretch where it
// fails, marked from the playhead. Nothing is saved until every Phrase is judged.
import type { components } from "../../api/schema";

type PhraseLabel = components["schemas"]["PhraseLabel"];

export interface Judgment {
  passed: boolean | null; // null until judged
  start: number | null; // s, for a fail
  end: number | null;
}

export const UNJUDGED: Judgment = { passed: null, start: null, end: null };

export function emptyDraft(phraseCount: number): Judgment[] {
  return Array.from({ length: phraseCount }, () => ({ ...UNJUDGED }));
}

function judgmentProblem(phrase: string, j: Judgment): string | null {
  if (j.passed === null) return `Judge “${phrase}”`;
  if (j.passed) return null;
  if (j.start === null || j.end === null) return `Mark where “${phrase}” fails: its start and end`;
  if (j.end < j.start) return `“${phrase}” ends before it starts`;
  return null;
}

/** Why the draft can't be saved yet, or null. `instruction` is null where none is needed. */
export function draftProblem(
  phrases: readonly string[],
  judgments: readonly Judgment[],
  instruction: string | null,
): string | null {
  for (const [i, phrase] of phrases.entries()) {
    const problem = judgmentProblem(phrase, judgments[i] ?? UNJUDGED);
    if (problem) return problem;
  }
  if (instruction?.trim() === "") return "Write the instruction it attempts";
  return null;
}

export function toPhraseLabels(
  phrases: readonly string[],
  judgments: readonly Judgment[],
): PhraseLabel[] {
  return phrases.map((phrase, i) => {
    const j = judgments[i];
    const failed = j?.passed === false && j.start !== null && j.end !== null;
    return {
      phrase,
      passed: !failed,
      interval: failed ? { start_s: j.start ?? 0, end_s: j.end ?? 0 } : null,
    };
  });
}
