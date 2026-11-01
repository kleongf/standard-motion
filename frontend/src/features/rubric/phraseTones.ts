// How each Phrase status reads, the same in the Description and on its section.
import type { PhraseStatus } from "./useDraft";

export const PHRASE_LABELS: Record<PhraseStatus, string> = {
  checked: "Checked",
  context: "Context",
  unsupported: "Unsupported",
};

export const PHRASE_TONES: Record<PhraseStatus, string> = {
  checked: "bg-sky-100 text-sky-950 dark:bg-sky-900/50 dark:text-sky-50",
  context: "bg-muted text-muted-foreground",
  unsupported: "bg-rose-100 text-rose-950 dark:bg-rose-900/50 dark:text-rose-50",
};

export const ASSUMED =
  "rounded border border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200";
