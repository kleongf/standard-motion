import { act, fireEvent, renderHook } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import type { Microphone, OpenMicrophone, Recording } from "./capture";
import { IDLE_MS, useMicrophone } from "./useMicrophone";
import { START_TIMEOUT_MS, STOP_TIMEOUT_MS, TOO_SHORT, usePushToTalk } from "./usePushToTalk";

const WAV = new Blob([new Uint8Array(44 + 32_000)], { type: "audio/wav" });
const SECOND: Recording = { wav: WAV, heldS: 1 };
// Held 50 ms: what is sent would be longer, with the pre-roll, but it isn't a word.
const BLIP: Recording = { wav: WAV, heldS: 0.05 };

/** A microphone that opens at once and whose turns go live with their first chunk, unless told
 * to wait. */
function fakeMic(turn: Recording = SECOND, options: { live?: boolean } = {}) {
  const stop = vi.fn(() => Promise.resolve(turn));
  const close = vi.fn(() => Promise.resolve());
  let goLive: () => void = () => undefined;
  const record = vi.fn((onLive: () => void) => {
    goLive = onLive;
    if (options.live ?? true) queueMicrotask(onLive);
    return { stop };
  });
  const open = vi.fn<OpenMicrophone>(() => Promise.resolve<Microphone>({ record, close }));
  return {
    open,
    record,
    stop,
    close,
    goLive: () => {
      goLive();
    },
  };
}

/** Push-to-talk with its own kept microphone, as the Review page gives it one. */
function renderTalk(open: OpenMicrophone, onTurn = vi.fn(), t = 0) {
  return renderHook(
    (props: { t: number }) =>
      usePushToTalk({ t: props.t, onTurn, microphone: useMicrophone(open) }),
    { initialProps: { t } },
  );
}

async function settle() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

const holdV = () => fireEvent.keyDown(globalThis.window, { key: "v", code: "KeyV" });
const releaseV = () => fireEvent.keyUp(globalThis.window, { key: "v", code: "KeyV" });

afterEach(() => {
  vi.useRealTimers();
});

test("holding V records a turn whose moment is the playhead when V went down", async () => {
  const mic = fakeMic();
  const onTurn = vi.fn();
  const { result, rerender } = renderTalk(mic.open, onTurn, 2.5);

  holdV();
  await settle();
  expect(result.current.phase).toBe("listening");
  rerender({ t: 4.0 }); // the video plays on while the reviewer talks
  releaseV();
  await settle();

  expect(result.current.phase).toBe("idle");
  expect(onTurn).toHaveBeenCalledExactlyOnceWith(WAV, 2.5);
});

test("Listening waits for the microphone's first audio; until then it is opening", async () => {
  const mic = fakeMic(SECOND, { live: false });
  const { result } = renderTalk(mic.open);

  holdV();
  await settle();
  expect(result.current.phase).toBe("opening");

  act(() => {
    mic.goLive();
  });
  expect(result.current.phase).toBe("listening");
});

test("a held key's repeats start no second turn", async () => {
  const mic = fakeMic();
  renderTalk(mic.open);

  holdV();
  fireEvent.keyDown(globalThis.window, { key: "v", code: "KeyV", repeat: true });
  holdV();
  await settle();

  expect(mic.record).toHaveBeenCalledTimes(1);
});

test("V while typing, or with a modifier, is left alone", () => {
  const mic = fakeMic();
  renderTalk(mic.open);
  const input = document.createElement("input");
  document.body.append(input);

  fireEvent.keyDown(input, { key: "v", code: "KeyV" });
  fireEvent.keyDown(globalThis.window, { key: "v", code: "KeyV", metaKey: true });

  expect(mic.open).not.toHaveBeenCalled();
  input.remove();
});

test("pressing and releasing the button records a turn too", async () => {
  const mic = fakeMic();
  const onTurn = vi.fn();
  const { result } = renderTalk(mic.open, onTurn, 1);

  act(() => {
    result.current.press();
  });
  await settle();
  act(() => {
    result.current.release();
  });
  await settle();

  expect(onTurn).toHaveBeenCalledExactlyOnceWith(WAV, 1);
});

test("a turn too short to hold a word says so and sends nothing", async () => {
  const mic = fakeMic(BLIP);
  const onTurn = vi.fn();
  const { result } = renderTalk(mic.open, onTurn);

  holdV();
  await settle();
  releaseV();
  await settle();

  expect(mic.stop).toHaveBeenCalled();
  expect(onTurn).not.toHaveBeenCalled();
  expect(result.current.error).toBe(TOO_SHORT);
  expect(TOO_SHORT).toBe("Too short to hear: hold V while you talk");
});

test("letting go before the microphone is live is too short, and ends the turn", async () => {
  const mic = fakeMic(SECOND, { live: false });
  const onTurn = vi.fn();
  const { result } = renderTalk(mic.open, onTurn);

  holdV();
  releaseV();
  await settle();

  expect(result.current.error).toBe(TOO_SHORT);
  expect(mic.stop).toHaveBeenCalled();
  expect(onTurn).not.toHaveBeenCalled();
});

test("a microphone that can't be opened is reported", async () => {
  const open = vi.fn<OpenMicrophone>(() => Promise.reject(new Error("Permission denied")));
  const { result } = renderTalk(open);

  holdV();
  await settle();

  expect(result.current.phase).toBe("idle");
  expect(result.current.error).toBe("The microphone couldn't be opened: Permission denied");
});

test("a microphone that never opens times out with a message", async () => {
  vi.useFakeTimers();
  const open = vi.fn<OpenMicrophone>(() => new Promise<Microphone>(() => undefined));
  const onTurn = vi.fn();
  const { result } = renderTalk(open, onTurn);

  holdV();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(START_TIMEOUT_MS);
  });

  expect(result.current.phase).toBe("idle");
  expect(result.current.error).toMatch(/^The microphone didn't start/);
  releaseV();
  await settle();
  expect(onTurn).not.toHaveBeenCalled();
});

test("a microphone that opens but never sends audio times out and is closed", async () => {
  vi.useFakeTimers();
  const mic = fakeMic(SECOND, { live: false });
  const { result } = renderTalk(mic.open);

  holdV();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(START_TIMEOUT_MS);
  });

  expect(result.current.error).toMatch(/^The microphone didn't start/);
  expect(mic.stop).toHaveBeenCalled();
  expect(mic.close).toHaveBeenCalled();
});

test("a microphone that never stops times out with a message", async () => {
  vi.useFakeTimers();
  const mic = fakeMic();
  mic.stop.mockImplementation(() => new Promise<Recording>(() => undefined));
  const onTurn = vi.fn();
  const { result } = renderTalk(mic.open, onTurn);

  holdV();
  await settle();
  releaseV();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(STOP_TIMEOUT_MS);
  });

  expect(result.current.error).toMatch(/^The turn couldn't be recorded/);
  expect(onTurn).not.toHaveBeenCalled();
  expect(mic.close).toHaveBeenCalled();
});

test("unmounting mid-turn ends the turn and closes the microphone", async () => {
  const mic = fakeMic();
  const onTurn = vi.fn();
  const { unmount } = renderTalk(mic.open, onTurn);

  holdV();
  await settle();
  unmount();
  await settle();

  expect(mic.stop).toHaveBeenCalled();
  expect(mic.close).toHaveBeenCalled();
  expect(onTurn).not.toHaveBeenCalled();
});

test("a second press records on the microphone already open", async () => {
  const mic = fakeMic();
  const onTurn = vi.fn();
  const { result } = renderTalk(mic.open, onTurn);

  for (const press of [1, 2]) {
    holdV();
    await settle();
    expect(result.current.phase, `press ${String(press)}`).toBe("listening");
    releaseV();
    await settle();
  }

  expect(onTurn).toHaveBeenCalledTimes(2);
  expect(mic.open).toHaveBeenCalledOnce();
  expect(mic.close).not.toHaveBeenCalled();
});

test("two minutes without a turn closes the microphone; the next press opens it again", async () => {
  vi.useFakeTimers();
  const mic = fakeMic();
  renderTalk(mic.open);
  holdV();
  await settle();
  releaseV();
  await settle();

  await act(async () => {
    await vi.advanceTimersByTimeAsync(IDLE_MS - 1);
  });
  expect(mic.close).not.toHaveBeenCalled();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1);
  });
  expect(mic.close).toHaveBeenCalledOnce();

  holdV();
  await settle();
  expect(mic.open).toHaveBeenCalledTimes(2);
});

test("a press within two minutes keeps the microphone open", async () => {
  vi.useFakeTimers();
  const mic = fakeMic();
  renderTalk(mic.open);
  holdV();
  await settle();
  releaseV();
  await settle();

  await act(async () => {
    await vi.advanceTimersByTimeAsync(IDLE_MS - 1000);
  });
  holdV();
  await settle();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(IDLE_MS); // still held
  });

  expect(mic.close).not.toHaveBeenCalled();
  expect(mic.open).toHaveBeenCalledOnce();
});
