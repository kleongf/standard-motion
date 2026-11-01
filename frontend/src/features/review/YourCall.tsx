// The Review Workstation's actions: only the Phrases Winnow couldn't decide, each answered Pass or
// Fail. Keys 1 and 2 answer the focused Phrase (the first, until another is clicked or picked with
// the arrow keys); each answer is saved as a `review` label, which recomputes the Episode's Triage
// decision.
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import type { LabelDraw } from "../labels/useLabels";
import type { ReviewItem } from "./useReview";

export type Answer = LabelDraw["value"];

const ANSWER_KEYS: Record<string, Answer> = { "1": "pass", "2": "fail" };
const MOVE_KEYS: Record<string, number> = { ArrowUp: -1, ArrowDown: 1 };

/** A key the panel may handle: not while typing, nor with a modifier held. */
function handled(event: KeyboardEvent): boolean {
  const target = event.target;
  const typing =
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement;
  return !typing && !event.metaKey && !event.ctrlKey && !event.altKey;
}

export function YourCall(props: {
  item: ReviewItem;
  pending: boolean;
  onAnswer: (phrase: string, value: Answer) => void;
}) {
  const { item, pending, onAnswer } = props;
  const [focused, setFocused] = useState(0);
  // An answered Phrase drops out of the list; keep the focus on one that's still there.
  const last = item.unsure.length - 1;
  const index = Math.min(focused, last);
  const focusedPhrase = item.unsure[index]?.phrase;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!handled(event)) return;
      const move = MOVE_KEYS[event.key];
      const value = ANSWER_KEYS[event.key];
      if (move !== undefined) {
        event.preventDefault();
        setFocused(Math.max(0, Math.min(last, index + move)));
      } else if (value && focusedPhrase && !pending && !event.repeat) {
        event.preventDefault();
        onAnswer(focusedPhrase, value);
      }
    };
    globalThis.addEventListener("keydown", onKey);
    return () => {
      globalThis.removeEventListener("keydown", onKey);
    };
  }, [index, last, focusedPhrase, pending, onAnswer]);

  return (
    <section
      aria-label="Your call"
      className="rounded-md border border-amber-300 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/40"
    >
      <div className="text-[11px] font-medium tracking-wide text-amber-800 uppercase dark:text-amber-300">
        Your call · {item.unsure.length} unsure Phrase{item.unsure.length === 1 ? "" : "s"}
      </div>
      <ul className="mt-1">
        {item.unsure.map((p, i) => (
          <li
            key={p.phrase}
            role="group"
            aria-label={p.phrase}
            aria-current={i === index ? "true" : undefined}
            onClick={() => {
              setFocused(i);
            }}
            onFocus={() => {
              setFocused(i); // tabbing onto its buttons focuses it too
            }}
            className={cn(
              "mt-1.5 cursor-pointer rounded px-2 py-1.5",
              i === index && "bg-background ring-1 ring-amber-400 dark:ring-amber-700",
            )}
          >
            <div className="text-sm leading-snug font-medium">“{p.phrase}”</div>
            <div className="mt-0.5 text-xs text-amber-900/80 dark:text-amber-200">
              {p.signals.join("; ")}
            </div>
            <div className="mt-1.5 flex gap-1.5">
              <AnswerButton
                label="Pass"
                shortcut={i === index ? "1" : null}
                disabled={pending}
                onClick={() => {
                  onAnswer(p.phrase, "pass");
                }}
              />
              <AnswerButton
                label="Fail"
                shortcut={i === index ? "2" : null}
                disabled={pending}
                onClick={() => {
                  onAnswer(p.phrase, "fail");
                }}
              />
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[11px] text-muted-foreground">
        Phrases that already passed or failed aren’t asked.
      </p>
    </section>
  );
}

function AnswerButton(props: {
  label: string;
  shortcut: string | null;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <Button size="xs" variant="outline" disabled={props.disabled} onClick={props.onClick}>
      <span>{props.label}</span>
      {props.shortcut && <kbd className="text-muted-foreground">{props.shortcut}</kbd>}
    </Button>
  );
}
