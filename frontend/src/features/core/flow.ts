// Where each numbered step stands, as short sidebar notes, and which step comes next: the first one
// with work waiting, in the order the work is done. `undefined` means still loading, so no step
// after it is picked yet.
import type { Page } from "./pages";

export interface FlowCounts {
  episodes?: number | undefined;
  /** Episodes with a first-pass Reference label: only theirs show results. */
  labelled?: number | undefined;
  /** The latest Rubric version Episodes are scored with, or null before there is one. */
  version?: number | null | undefined;
  /** Episodes with results, out of `labelled`. */
  shown?: number | undefined;
  /** Needs review Episodes left in the queue. */
  waiting?: number | undefined;
  /** Audit sample items left to mark, or null before a sample is drawn. */
  auditLeft?: number | null | undefined;
}

/** Each step's "has work waiting", or undefined while its count loads. */
const WAITING: [Page, (c: FlowCounts) => boolean | undefined][] = [
  ["prepare", (c) => (c.episodes === undefined ? undefined : c.episodes === 0)],
  ["reference", (c) => (c.labelled === undefined ? undefined : c.labelled === 0)],
  ["describe", (c) => (c.version === undefined ? undefined : c.version === null)],
  ["review", (c) => (c.waiting === undefined ? undefined : c.waiting > 0)],
  ["audit", (c) => (c.auditLeft === undefined ? undefined : c.auditLeft !== 0)],
];

export function nextStep(c: FlowCounts): Page | null {
  for (const [page, waiting] of WAITING) {
    const w = waiting(c);
    if (w === undefined) return null;
    if (w) return page;
  }
  return null;
}

function count(n: number | undefined, text: (n: number) => string): string | undefined {
  return n === undefined ? undefined : text(n);
}

function versionNote(version: number | null | undefined): string | undefined {
  if (version === undefined) return undefined;
  return version === null ? "no Rubric" : `v${String(version)}`;
}

/** "done" only once there could have been something to review. */
function reviewNote(c: FlowCounts): string | undefined {
  if (c.waiting === undefined) return undefined;
  if (c.waiting > 0) return `${String(c.waiting)} waiting`;
  return c.labelled && c.version ? "done" : undefined;
}

function auditNote(left: number | null | undefined): string | undefined {
  if (left === undefined) return undefined;
  if (left === null) return "not drawn";
  return left === 0 ? "done" : `${String(left)} left`;
}

export function stepNotes(c: FlowCounts): Partial<Record<Page, string | undefined>> {
  return {
    prepare: count(c.episodes, (n) => `${String(n)} Episode${n === 1 ? "" : "s"}`),
    reference:
      c.labelled === undefined || c.episodes === undefined
        ? undefined
        : `${String(c.labelled)} of ${String(c.episodes)}`,
    describe: versionNote(c.version),
    episodes: count(c.shown, (n) => `${String(n)} decided`),
    review: reviewNote(c),
    audit: auditNote(c.auditLeft),
  };
}
