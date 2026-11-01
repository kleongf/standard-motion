// What a voice turn decided, one chip per unsure Phrase, for the reviewer to confirm (saved as an
// ordinary `review` label) or discard. The moment is the playhead when the turn began.
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import type { VoiceChip } from "./useVoice";

export interface HeardChip extends VoiceChip {
  id: number;
  t: number;
}

export function VoiceChips(props: {
  chips: HeardChip[];
  pending: boolean;
  onConfirm: (chip: HeardChip) => void;
  onDiscard: (chip: HeardChip) => void;
  onSeek: (t: number) => void;
}) {
  const { chips, pending } = props;
  if (chips.length === 0) return null;
  return (
    <ul className="mt-2 space-y-1.5">
      {chips.map((chip) => (
        <li
          key={chip.id}
          role="group"
          aria-label={chip.phrase}
          className="rounded border bg-background px-2 py-1.5"
        >
          <div className="flex items-start gap-2">
            <span
              className={cn(
                "mt-0.5 rounded px-1.5 text-[11px] font-medium",
                chip.value === "pass"
                  ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                  : "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
              )}
            >
              {chip.value === "pass" ? "Pass" : "Fail"}
            </span>
            <span className="text-sm leading-snug font-medium">“{chip.phrase}”</span>
          </div>
          <div className="mt-1 flex items-baseline gap-2 text-xs text-muted-foreground">
            <span className="min-w-0 italic">“{chip.quote}”</span>
            <button
              type="button"
              aria-label={`Seek to ${chip.t.toFixed(1)} s`}
              className="ml-auto shrink-0 tabular-nums underline-offset-2 hover:underline"
              onClick={() => {
                props.onSeek(chip.t);
              }}
            >
              at {chip.t.toFixed(1)} s
            </button>
          </div>
          <div className="mt-1.5 flex gap-1.5">
            <Button
              size="xs"
              disabled={pending}
              onClick={() => {
                props.onConfirm(chip);
              }}
            >
              Confirm
            </Button>
            <Button
              size="xs"
              variant="ghost"
              onClick={() => {
                props.onDiscard(chip);
              }}
            >
              Discard
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
}
