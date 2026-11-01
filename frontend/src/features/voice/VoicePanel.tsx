// Voice labeling on the Review page: hold V (or the mic button) and narrate while the Episode
// plays. Each turn comes back as chips on the Episode's unsure Phrases; voice is only the input
// mode, so a confirmed chip is saved like a Pass or Fail from "Your call".
import { Mic } from "lucide-react";
import { useCallback, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

import type { Playhead } from "../episodes/usePlayhead";
import type { StartCapture } from "./capture";
import { usePushToTalk, type TalkPhase } from "./usePushToTalk";
import { useVoiceTurn } from "./useVoice";
import { VoiceChips, type HeardChip } from "./VoiceChips";

export function VoicePanel(props: {
  episodeId: string;
  unsure: string[];
  playhead: Playhead;
  saving: boolean;
  onConfirm: (phrase: string, value: HeardChip["value"]) => void;
  start?: StartCapture; // the microphone; tests pass a fake one
}) {
  const { episodeId, playhead } = props;
  const turn = useVoiceTurn();
  const [chips, setChips] = useState<HeardChip[]>([]);
  const [heard, setHeard] = useState<string | null>(null);
  const nextId = useRef(1);
  const { mutate } = turn;

  const onTurn = useCallback(
    (wav: Blob, t: number) => {
      mutate(
        { episodeId, wav, t },
        {
          onSuccess: (answer) => {
            setHeard(answer.transcript);
            const added = answer.chips.map((c) => ({ ...c, t: answer.t, id: nextId.current++ }));
            // A newer turn on the same Phrase replaces the older chip.
            setChips((was) => [
              ...was.filter((c) => !added.some((a) => a.phrase === c.phrase)),
              ...added,
            ]);
          },
        },
      );
    },
    [mutate, episodeId],
  );
  const talk = usePushToTalk({ t: playhead.t, onTurn, start: props.start });
  const drop = (chip: HeardChip) => {
    setChips((was) => was.filter((c) => c.id !== chip.id));
  };
  // A Phrase answered another way is no longer unsure: its chip goes with it.
  const shown = chips.filter((c) => props.unsure.includes(c.phrase));

  return (
    <section aria-label="Voice" className="-mt-2 mb-5 rounded-md border p-3">
      <TalkButton talk={talk} hearing={turn.isPending} />
      {heard !== null && (
        <p className="mt-2 text-xs text-muted-foreground" data-testid="voice-heard">
          Heard: “{heard}”{!turn.isPending && shown.length === 0 && " · no unsure Phrase in it"}
        </p>
      )}
      {(talk.error ?? turn.error) && (
        <p className="mt-2 text-xs text-destructive" role="alert">
          {talk.error ?? turn.error?.message}
        </p>
      )}
      <VoiceChips
        chips={shown}
        pending={props.saving}
        onConfirm={(chip) => {
          props.onConfirm(chip.phrase, chip.value);
          drop(chip);
        }}
        onDiscard={drop}
        onSeek={playhead.seek}
      />
    </section>
  );
}

const TALK_LABEL: Record<TalkPhase, string> = {
  idle: "Hold to talk",
  opening: "Opening the mic…",
  listening: "Listening…",
};

/** Held down, it records a turn, as V does. */
function TalkButton(props: {
  talk: { phase: TalkPhase; press: () => void; release: () => void };
  hearing: boolean;
}) {
  const { talk } = props;
  return (
    <div className="flex items-center gap-2">
      <Button
        size="sm"
        variant={talk.phase === "idle" ? "outline" : "default"}
        aria-pressed={talk.phase !== "idle"}
        onPointerDown={talk.press}
        onPointerUp={talk.release}
        onPointerLeave={talk.release}
      >
        <Mic />
        <span>{TALK_LABEL[talk.phase]}</span>
        <kbd className="text-muted-foreground">V</kbd>
      </Button>
      <span className="text-xs text-muted-foreground" role="status">
        {props.hearing ? "Hearing…" : "Narrate while it plays"}
      </span>
    </div>
  );
}
