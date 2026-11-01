// The Review page's microphone, kept open between push-to-talk turns so each press records at
// once, with the pre-roll from just before it. It opens on the first press and closes after
// IDLE_MS without a turn, or when the page goes.
import { useEffect, useState, useSyncExternalStore } from "react";

import { openMicrophone, type Microphone, type OpenMicrophone } from "./capture";

export const IDLE_MS = 2 * 60 * 1000;

export interface KeptMicrophone {
  /** The open microphone, opened if it isn't; holds off the idle close. */
  get: () => Promise<Microphone>;
  /** Not in use: it closes after IDLE_MS unless it is got again first. */
  rest: () => void;
  close: () => void;
  isOn: () => boolean;
  subscribe: (listener: () => void) => () => void;
}

export function keepMicrophone(open: OpenMicrophone): KeptMicrophone {
  let current: Promise<Microphone> | null = null;
  let on = false;
  let idle: ReturnType<typeof setTimeout> | undefined;
  const listeners = new Set<() => void>();

  const switched = (value: boolean) => {
    if (on === value) return;
    on = value;
    listeners.forEach((listener) => {
      listener();
    });
  };

  const close = () => {
    clearTimeout(idle);
    const was = current;
    current = null;
    switched(false);
    void was?.then((mic) => mic.close()).catch(() => undefined);
  };

  const get = () => {
    clearTimeout(idle);
    if (current) return current;
    const opening: Promise<Microphone> = open(() => {
      if (current === opening) close();
    });
    current = opening;
    opening.then(
      () => {
        if (current === opening) switched(true);
      },
      () => {
        if (current === opening) current = null; // the next press tries again
      },
    );
    return opening;
  };

  return {
    get,
    rest: () => {
      clearTimeout(idle);
      idle = setTimeout(close, IDLE_MS);
    },
    close,
    isOn: () => on,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
}

/** A microphone kept for as long as the calling component is mounted. */
export function useMicrophone(open: OpenMicrophone = openMicrophone): KeptMicrophone {
  const [kept] = useState(() => keepMicrophone(open));
  useEffect(
    () => () => {
      kept.close();
    },
    [kept],
  );
  return kept;
}

/** Whether the kept microphone is open, for the reviewer to see. */
export function useMicrophoneOn(kept: KeptMicrophone): boolean {
  return useSyncExternalStore(kept.subscribe, kept.isOn);
}
