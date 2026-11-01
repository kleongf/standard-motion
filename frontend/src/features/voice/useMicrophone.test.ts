// The kept microphone with the real `openMicrophone`, over a fake browser microphone: what the
// browser is asked to open, and when its stream is closed.
import { act, fireEvent, renderHook } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { stubWebAudio } from "./fakeWebAudio";
import { IDLE_MS, useMicrophone, useMicrophoneOn } from "./useMicrophone";
import { usePushToTalk } from "./usePushToTalk";

const holdV = () => fireEvent.keyDown(globalThis.window, { key: "v", code: "KeyV" });
const releaseV = () => fireEvent.keyUp(globalThis.window, { key: "v", code: "KeyV" });

async function settle() {
  await act(async () => {
    for (let i = 0; i < 10; i++) await Promise.resolve();
  });
}

function renderReview(onTurn = vi.fn()) {
  return renderHook(() => {
    const microphone = useMicrophone();
    return {
      talk: usePushToTalk({ t: 0, onTurn, microphone }),
      on: useMicrophoneOn(microphone),
    };
  });
}

/** Hold V and talk for `seconds`, then let go. */
async function turn(audio: ReturnType<typeof stubWebAudio>, seconds = 1) {
  holdV();
  await settle();
  act(() => {
    audio.play(seconds);
  });
  releaseV();
  await settle();
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("a second press doesn't ask the browser for the microphone again", async () => {
  const audio = stubWebAudio();
  const onTurn = vi.fn();
  const { result } = renderReview(onTurn);

  await turn(audio);
  expect(result.current.on).toBe(true);
  holdV();
  await settle();
  act(() => {
    audio.play(0.01); // the next render quantum
  });
  expect(result.current.talk.phase).toBe("listening");
  act(() => {
    audio.play(1);
  });
  releaseV();
  await settle();

  expect(audio.getUserMedia).toHaveBeenCalledOnce();
  expect(onTurn).toHaveBeenCalledTimes(2);
  expect(audio.tracks[0]?.stop).not.toHaveBeenCalled();
});

test("two minutes idle closes the microphone's stream", async () => {
  vi.useFakeTimers();
  const audio = stubWebAudio();
  const { result } = renderReview();
  await turn(audio);

  await act(async () => {
    await vi.advanceTimersByTimeAsync(IDLE_MS);
  });

  expect(audio.tracks[0]?.stop).toHaveBeenCalled();
  expect(audio.contexts[0]?.close).toHaveBeenCalled();
  expect(result.current.on).toBe(false);
});

test("leaving the page closes the microphone's stream", async () => {
  const audio = stubWebAudio();
  const { unmount } = renderReview();
  await turn(audio);

  unmount();
  await settle();

  expect(audio.tracks[0]?.stop).toHaveBeenCalled();
  expect(audio.contexts[0]?.close).toHaveBeenCalled();
});

test("a microphone unplugged between turns is opened afresh on the next press", async () => {
  const audio = stubWebAudio();
  const { result } = renderReview();
  await turn(audio);

  act(() => {
    audio.tracks[0]?.end();
  });
  await settle();
  expect(result.current.on).toBe(false);
  await turn(audio);

  expect(audio.getUserMedia).toHaveBeenCalledTimes(2);
  expect(result.current.on).toBe(true);
});
