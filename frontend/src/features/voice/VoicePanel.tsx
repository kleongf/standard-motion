// Voice labeling on the Review page: hold V (or the mic button) and narrate while the Episode
// plays. Each turn comes back as chips on the Episode's unsure Phrases; voice is only the input
// mode, so a confirmed chip is saved like a Pass or Fail from "Your call".
import { Mic } from "lucide-react";
import { useCallback, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

import { useHealth } from "../core/useHealth";
import type { Playhead } from "../episodes/usePlayhead";
import { useMicrophoneOn, type KeptMicrophone } from "./useMicrophone";
import { usePushToTalk, type TalkPhase } from "./usePushToTalk";
import { useVoiceTurn, type VoiceTurn } from "./useVoice";
import { VoiceChips, type HeardChip } from "./VoiceChips";

interface Props {
  episodeId: string;
  unsure: string[];
  playhead: Playhead;
  saving: boolean;
  /** Saves the chip's answer as a `review` label; the chip leaves once it resolves. */
  onConfirm: (phrase: string, value: HeardChip["value"]) => Promise<unknown>;
  /** The page's microphone (`useMicrophone`), kept open across Episodes between turns. */
  microphone: KeptMicrophone;
}

/** Shown only when the Meta API (or a replay of it) can hear a turn: without it, V does
 * nothing. */
export function VoicePanel(props: Props) {
  const health = useHealth();
  return health.data?.meta_available ? <Voice {...props} /> : null;
}

/** The turns heard so far, each landing on its own: a turn heard later than the next one began
 * still adds its chips. */
function useHeardTurns(episodeId: string) {
  const { mutateAsync } = useVoiceTurn();
  const [chips, setChips] = useState<HeardChip[]>([]);
  const [heard, setHeard] = useState<string | null>(null);
  const [hearing, setHearing] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const nextId = useRef(1);

  const land = useCallback((answer: VoiceTurn) => {
    setHeard(answer.transcript);
    const added = answer.chips.map((c) => ({ ...c, t: answer.t, id: nextId.current++ }));
    // A newer turn on the same Phrase replaces the older chip.
    setChips((was) => [...was.filter((c) => !added.some((a) => a.phrase === c.phrase)), ...added]);
  }, []);

  const onTurn = useCallback(
    (wav: Blob, t: number) => {
      setError(null);
      setHearing((n) => n + 1);
      mutateAsync({ episodeId, wav, t })
        .then(land, (e: unknown) => {
          setError(e instanceof Error ? e.message : String(e));
        })
        .finally(() => {
          setHearing((n) => n - 1);
        });
    },
    [mutateAsync, episodeId, land],
  );
  const drop = useCallback((chip: HeardChip) => {
    setChips((was) => was.filter((c) => c.id !== chip.id));
  }, []);
  return { chips, heard, hearing: hearing > 0, error, onTurn, drop };
}

function Voice(props: Props) {
  const { playhead } = props;
  const turns = useHeardTurns(props.episodeId);
  const talk = usePushToTalk({
    t: playhead.t,
    onTurn: turns.onTurn,
    microphone: props.microphone,
  });
  // A Phrase answered another way is no longer unsure: its chip goes with it.
  const shown = turns.chips.filter((c) => props.unsure.includes(c.phrase));
  const error = talk.error ?? turns.error;

  return (
    <section aria-label="Voice" className="-mt-2 mb-5 rounded-md border p-3">
      <TalkButton talk={talk} hearing={turns.hearing} microphone={props.microphone} />
      {turns.heard !== null && (
        <p className="mt-2 text-xs text-muted-foreground" data-testid="voice-heard">
          Heard: “{turns.heard}”
          {!turns.hearing && shown.length === 0 && " · no unsure Phrase in it"}
        </p>
      )}
      {error && (
        <p className="mt-2 text-xs text-destructive" role="alert">
          {error}
        </p>
      )}
      <VoiceChips
        chips={shown}
        pending={props.saving}
        onConfirm={(chip) => {
          // A failed save keeps the chip, to confirm again; the save's error shows beside it.
          props.onConfirm(chip.phrase, chip.value).then(
            () => {
              turns.drop(chip);
            },
            () => undefined,
          );
        }}
        onDiscard={turns.drop}
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
  microphone: KeptMicrophone;
}) {
  const { talk } = props;
  const micOn = useMicrophoneOn(props.microphone);
  return (
    <>
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
      {micOn && (
        <p
          className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground"
          title="It stays open between turns, so each press records at once, and closes after 2 minutes without a turn or when you leave Review"
          data-testid="mic-on"
        >
          <span aria-hidden className="size-1.5 rounded-full bg-red-500" />
          Mic on · closes after 2 min idle
        </p>
      )}
    </>
  );
}
