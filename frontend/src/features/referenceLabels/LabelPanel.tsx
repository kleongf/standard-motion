// The label panel in the Workstation's actions slot: the per-Episode timer, a judgment per
// Phrase of the frozen Description, the instruction where the Episode has none, and its box.
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

import type { Episode } from "../episodes/useEpisodes";
import type { Playhead } from "../episodes/usePlayhead";
import { draftProblem, emptyDraft, toPhraseLabels, UNJUDGED, type Judgment } from "./labelDraft";
import { LabelBox } from "./LabelBox";
import { PhraseJudgment } from "./PhraseJudgment";
import { clock, useElapsed } from "./useElapsed";
import { useSaveReferenceLabel } from "./useReferenceLabels";

export function LabelPanel(props: {
  episode: Episode;
  phrases: string[];
  playhead: Playhead;
  relabel: boolean;
  onSaved: () => void;
}) {
  const { episode, phrases, relabel } = props;
  const elapsed = useElapsed();
  const [judgments, setJudgments] = useState<Judgment[]>(() => emptyDraft(phrases.length));
  const needsInstruction = episode.instruction === null;
  const [instruction, setInstruction] = useState("");
  const save = useSaveReferenceLabel();
  const problem = draftProblem(phrases, judgments, needsInstruction ? instruction : null);

  const submit = () => {
    if (problem || save.isPending) return;
    const draw = {
      phrases: toPhraseLabels(phrases, judgments),
      instruction: needsInstruction ? instruction.trim() : null,
      elapsed_s: Math.round(elapsed.read() * 10) / 10,
      relabel,
    };
    save.mutate({ episodeId: episode.id, draw }, { onSuccess: props.onSaved });
  };

  return (
    <section aria-label="Reference label" className="border-b pb-4">
      <div className="flex items-baseline gap-2">
        <h2 className="text-sm font-semibold">{relabel ? "Relabel" : "Reference label"}</h2>
        <span
          className="ml-auto text-xs text-muted-foreground tabular-nums"
          data-testid="label-timer"
          title="Time on this Episode"
        >
          {clock(elapsed.seconds)}
        </span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Judge each Phrase from the video alone. For a fail, scrub to where it starts and ends.
      </p>
      <ul className="mt-2">
        {phrases.map((phrase, i) => (
          <PhraseJudgment
            key={phrase}
            phrase={phrase}
            judgment={judgments[i] ?? UNJUDGED}
            playhead={props.playhead}
            onChange={(next) => {
              setJudgments(judgments.map((j, k) => (k === i ? next : j)));
            }}
          />
        ))}
      </ul>
      {needsInstruction && (
        <label className="mt-3 block text-xs font-medium">
          Instruction <span className="font-normal text-muted-foreground">(none recorded)</span>
          <Textarea
            className="mt-1 min-h-12 text-sm"
            placeholder="The task this Episode attempts, e.g. Put the marker in the cup"
            value={instruction}
            onChange={(event) => {
              setInstruction(event.target.value);
            }}
          />
        </label>
      )}
      {!relabel && <LabelBox episode={episode} />}
      {save.error && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {save.error.message}
        </p>
      )}
      <div className="mt-3 flex items-center gap-2">
        <span className="flex-1 text-xs text-muted-foreground">{problem}</span>
        <Button size="sm" disabled={problem !== null || save.isPending} onClick={submit}>
          Save & next
        </Button>
      </div>
    </section>
  );
}
