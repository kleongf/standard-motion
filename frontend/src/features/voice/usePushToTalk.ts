// Push-to-talk: hold V (Space, 1, 2 and the arrows are the Workstation's and Your call's), or
// press and hold the mic button. The turn's moment is the playhead when it began: Voice
// Transcribe gives no word timestamps. No turn ends without a word: it is sent, or the reviewer
// is told why not.
import { useCallback, useEffect, useRef, useState } from "react";

import { startCapture, type Capture, type StartCapture } from "./capture";
import { TARGET_RATE } from "./wav";

const MIN_TURN_S = 0.3; // shorter is a slip of the key, not a word
const MIN_BYTES = 44 + MIN_TURN_S * TARGET_RATE * 2;
export const START_TIMEOUT_MS = 5000;
export const STOP_TIMEOUT_MS = 5000;
export const TOO_SHORT = "Too short to hear: hold V while you talk";
const NO_START =
  "The microphone didn't start: check that it's connected and allowed, then hold V again";

/** Opening until the microphone's first audio arrives; only then is it listening. */
export type TalkPhase = "idle" | "opening" | "listening";

interface Turn {
  t: number;
  live: boolean;
  capture: Promise<Capture>;
  timer?: ReturnType<typeof setTimeout>;
}

function isTalkKey(event: KeyboardEvent): boolean {
  const target = event.target;
  const typing =
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement;
  const modified = event.metaKey || event.ctrlKey || event.altKey;
  return event.code === "KeyV" && !typing && !modified;
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/** Close a turn's microphone whenever it opens, throwing its audio away. */
function discard(turn: Turn) {
  turn.capture.then((capture) => capture.stop()).catch(() => undefined);
}

function within<T>(promise: Promise<T>, ms: number, why: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(why));
    }, ms);
    promise.then(resolve, reject).finally(() => {
      clearTimeout(timer);
    });
  });
}

export function usePushToTalk(options: {
  t: number;
  onTurn: (wav: Blob, t: number) => void;
  start?: StartCapture | undefined;
}) {
  const { onTurn, start = startCapture } = options;
  const [phase, setPhase] = useState<TalkPhase>("idle");
  const [error, setError] = useState<string | null>(null);
  const t = useRef(options.t);
  const turn = useRef<Turn | null>(null); // the turn being held
  const latest = useRef<Turn | null>(null); // the last turn begun, held or not
  const mounted = useRef(true);

  useEffect(() => {
    t.current = options.t;
  }, [options.t]);

  /** End the held turn, if it is still `ending`, sending nothing. */
  const abandon = useCallback((ending: Turn, why: string) => {
    if (turn.current !== ending) return;
    turn.current = null;
    clearTimeout(ending.timer);
    setPhase("idle");
    setError(why);
    discard(ending);
  }, []);

  const press = useCallback(() => {
    if (turn.current) return;
    setError(null);
    let ending: Turn | undefined = undefined;
    const capture = start(() => {
      if (!ending || turn.current !== ending || ending.live) return;
      ending.live = true;
      clearTimeout(ending.timer);
      setPhase("listening");
    });
    ending = { t: t.current, live: false, capture };
    turn.current = latest.current = ending;
    ending.capture.catch((e: unknown) => {
      if (latest.current !== ending) return; // a newer turn speaks for itself
      if (turn.current === ending) turn.current = null;
      clearTimeout(ending.timer);
      setPhase("idle");
      setError(`The microphone couldn't be opened: ${message(e)}`);
    });
    ending.timer = setTimeout(() => {
      abandon(ending, NO_START);
    }, START_TIMEOUT_MS);
    setPhase("opening");
  }, [start, abandon]);

  const finish = useCallback(
    async (ending: Turn) => {
      try {
        const capture = await ending.capture;
        const wav = await within(capture.stop(), STOP_TIMEOUT_MS, "the microphone didn't stop");
        if (!mounted.current) return;
        if (wav.size < MIN_BYTES) setError(TOO_SHORT);
        else onTurn(wav, ending.t);
      } catch (e) {
        if (mounted.current) setError(`The turn couldn't be recorded: ${message(e)}`);
      }
    },
    [onTurn],
  );

  const release = useCallback(() => {
    const ending = turn.current;
    if (!ending) return;
    turn.current = null;
    clearTimeout(ending.timer);
    setPhase("idle");
    if (ending.live) {
      void finish(ending);
      return;
    }
    setError(TOO_SHORT); // let go before the microphone heard anything
    discard(ending);
  }, [finish]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      const ending = turn.current;
      turn.current = null;
      if (ending) {
        clearTimeout(ending.timer);
        discard(ending);
      }
    };
  }, []);

  useEffect(() => {
    const down = (event: KeyboardEvent) => {
      if (!isTalkKey(event)) return;
      event.preventDefault();
      if (!event.repeat) press();
    };
    const up = (event: KeyboardEvent) => {
      if (event.code === "KeyV") release();
    };
    globalThis.addEventListener("keydown", down);
    globalThis.addEventListener("keyup", up);
    globalThis.addEventListener("blur", release); // a key released in another window never says
    return () => {
      globalThis.removeEventListener("keydown", down);
      globalThis.removeEventListener("keyup", up);
      globalThis.removeEventListener("blur", release);
    };
  }, [press, release]);

  return { phase, error, press, release };
}
