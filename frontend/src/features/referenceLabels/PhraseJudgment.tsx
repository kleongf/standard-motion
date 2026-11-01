// One Phrase of the frozen Description: pass or fail, and for a fail the stretch where it fails,
// marked by scrubbing the playhead to its start and end.
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import type { Playhead } from "../episodes/usePlayhead";
import type { Judgment } from "./labelDraft";

export function PhraseJudgment(props: {
  phrase: string;
  judgment: Judgment;
  playhead: Playhead;
  onChange: (judgment: Judgment) => void;
}) {
  const { judgment: j, playhead, onChange } = props;
  const choice = (passed: boolean, label: string) => (
    <Button
      size="xs"
      variant={j.passed === passed ? (passed ? "default" : "destructive") : "outline"}
      aria-pressed={j.passed === passed}
      onClick={() => {
        onChange({ ...j, passed });
      }}
    >
      {label}
    </Button>
  );
  const mark = (edge: "start" | "end") => {
    const value = j[edge];
    return (
      <Button
        size="xs"
        variant="outline"
        className={cn("tabular-nums", value === null && "text-muted-foreground")}
        onClick={() => {
          onChange({ ...j, [edge]: Number(playhead.t.toFixed(2)) });
        }}
      >
        {value === null
          ? `Mark ${edge}`
          : `${edge === "start" ? "Start" : "End"} ${value.toFixed(1)} s`}
      </Button>
    );
  };

  return (
    <li role="group" aria-label={props.phrase} className="border-t py-2 first:border-t-0">
      <div className="flex items-start gap-2">
        <span className="flex-1 text-sm leading-snug">{props.phrase}</span>
        {choice(true, "Pass")}
        {choice(false, "Fail")}
      </div>
      {j.passed === false && (
        <div className="mt-1.5 flex items-center gap-1.5 text-xs text-muted-foreground">
          <span>Fails from</span>
          {mark("start")}
          <span>to</span>
          {mark("end")}
          {j.start !== null && (
            <button
              type="button"
              className="ml-auto underline-offset-2 hover:underline"
              onClick={() => {
                playhead.seek(j.start ?? 0);
              }}
            >
              Seek
            </button>
          )}
        </div>
      )}
    </li>
  );
}
