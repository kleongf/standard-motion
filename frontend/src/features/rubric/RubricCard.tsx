// The Rubric draft as a card in the conversation, updated in place: every edit, recompile and
// interview answer changes it where it stands. Its header counts what it holds and what Spark
// still assumes; it folds away to keep the conversation short.
import { ChevronDown, FileText } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

import { Pill } from "../triage/Pill";
import { type DraftEditing, RubricPanel } from "./RubricPanel";
import type { RubricDraft } from "./useDraft";

export const RUBRIC_CARD_ID = "rubric-draft";

function plural(n: number, one: string, many: string): string {
  return `${String(n)} ${n === 1 ? one : many}`;
}

export function scrollToRubric(): void {
  document.getElementById(RUBRIC_CARD_ID)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function RubricCard(props: {
  draft: RubricDraft;
  editing: DraftEditing;
  highlighted: string | null;
  error?: Error | null;
}) {
  const { draft } = props;
  const [open, setOpen] = useState(true);
  const assumed = draft.assumptions_unconfirmed;
  return (
    <section
      id={RUBRIC_CARD_ID}
      aria-label="Rubric draft"
      className="scroll-mt-24 overflow-hidden rounded-xl border bg-card shadow-sm"
    >
      <button
        type="button"
        aria-expanded={open}
        onClick={() => {
          setOpen((o) => !o);
        }}
        className="flex w-full items-center gap-2 px-4 py-3 text-left hover:bg-muted/50"
      >
        <FileText className="size-4 text-muted-foreground" />
        <span className="text-sm font-semibold">Rubric draft</span>
        <span className="text-xs text-muted-foreground">
          {plural(draft.phrases.length, "Phrase", "Phrases")} ·{" "}
          {plural(draft.criteria.length, "Criterion", "Criteria")}
        </span>
        <span className="flex-1" />
        {assumed > 0 && <Pill tone="unsure">{assumed} assumed</Pill>}
        <ChevronDown
          className={cn("size-4 text-muted-foreground transition-transform", !open && "-rotate-90")}
        />
      </button>
      <div className={cn("border-t px-4 pt-4 pb-5", !open && "hidden")}>
        {props.error && <p className="mb-2 text-sm text-destructive">{props.error.message}</p>}
        <RubricPanel draft={draft} editing={props.editing} highlighted={props.highlighted} />
      </div>
    </section>
  );
}
