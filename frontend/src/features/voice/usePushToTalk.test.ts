import { act, fireEvent, renderHook } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import type { Capture, StartCapture } from "./capture";
import { START_TIMEOUT_MS, STOP_TIMEOUT_MS, TOO_SHORT, usePushToTalk } from "./usePushToTalk";

const SECOND = new Blob([new Uint8Array(44 + 32_000)], { type: "audio/wav" });
const BLIP = new Blob([new Uint8Array(44 + 1600)], { type: "audio/wav" }); // 50 ms

/** A microphone that opens at once and goes live with its first chunk, unless told to wait. */
function fakeMic(turn: Blob = SECOND, options: { live?: boolean } = {}) {
  const stop = vi.fn(() => Promise.resolve(turn));
  let goLive: () => void = () => undefined;
  const start = vi.fn((onLive: () => void) => {
    goLive = onLive;
    if (options.live ?? true) queueMicrotask(onLive);
    return Promise.resolve<Capture>({ stop });
  });
  return {
    start,
    stop,
    goLive: () => {
      goLive();
    },
  };
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
  const { result, rerender } = renderHook(
    (props: { t: number }) => usePushToTalk({ t: props.t, onTurn, start: mic.start }),
    { initialProps: { t: 2.5 } },
  );

  holdV();
  await settle();
  expect(result.current.phase).toBe("listening");
  rerender({ t: 4.0 }); // the video plays on while the reviewer talks
  releaseV();
  await settle();

  expect(result.current.phase).toBe("idle");
  expect(onTurn).toHaveBeenCalledExactlyOnceWith(SECOND, 2.5);
});

test("Listening waits for the microphone's first audio; until then it is opening", async () => {
  const mic = fakeMic(SECOND, { live: false });
  const { result } = renderHook(() => usePushToTalk({ t: 0, onTurn: vi.fn(), start: mic.start }));

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
  renderHook(() => usePushToTalk({ t: 0, onTurn: vi.fn(), start: mic.start }));

  holdV();
  fireEvent.keyDown(globalThis.window, { key: "v", code: "KeyV", repeat: true });
  holdV();
  await settle();

  expect(mic.start).toHaveBeenCalledTimes(1);
});

test("V while typing, or with a modifier, is left alone", () => {
  const mic = fakeMic();
  renderHook(() => usePushToTalk({ t: 0, onTurn: vi.fn(), start: mic.start }));
  const input = document.createElement("input");
  document.body.append(input);

  fireEvent.keyDown(input, { key: "v", code: "KeyV" });
  fireEvent.keyDown(globalThis.window, { key: "v", code: "KeyV", metaKey: true });

  expect(mic.start).not.toHaveBeenCalled();
  input.remove();
});

test("pressing and releasing the button records a turn too", async () => {
  const mic = fakeMic();
  const onTurn = vi.fn();
  const { result } = renderHook(() => usePushToTalk({ t: 1, onTurn, start: mic.start }));

  act(() => {
    result.current.press();
  });
  await settle();
  act(() => {
    result.current.release();
  });
  await settle();

  expect(onTurn).toHaveBeenCalledExactlyOnceWith(SECOND, 1);
});

test("a turn too short to hold a word says so and sends nothing", async () => {
  const mic = fakeMic(BLIP);
  const onTurn = vi.fn();
  const { result } = renderHook(() => usePushToTalk({ t: 0, onTurn, start: mic.start }));

  holdV();
  await settle();
  releaseV();
  await settle();

  expect(mic.stop).toHaveBeenCalled();
  expect(onTurn).not.toHaveBeenCalled();
  expect(result.current.error).toBe(TOO_SHORT);
  expect(TOO_SHORT).toBe("Too short to hear: hold V while you talk");
});

test("letting go before the microphone is live is too short, and closes it", async () => {
  const mic = fakeMic(SECOND, { live: false });
  const onTurn = vi.fn();
  const { result } = renderHook(() => usePushToTalk({ t: 0, onTurn, start: mic.start }));

  holdV();
  releaseV();
  await settle();

  expect(result.current.error).toBe(TOO_SHORT);
  expect(mic.stop).toHaveBeenCalled();
  expect(onTurn).not.toHaveBeenCalled();
});

test("a microphone that can't be opened is reported", async () => {
  const start = vi.fn<StartCapture>(() => Promise.reject(new Error("Permission denied")));
  const { result } = renderHook(() => usePushToTalk({ t: 0, onTurn: vi.fn(), start }));

  holdV();
  await settle();

  expect(result.current.phase).toBe("idle");
  expect(result.current.error).toBe("The microphone couldn't be opened: Permission denied");
});

test("a microphone that never opens times out with a message", async () => {
  vi.useFakeTimers();
  const start = vi.fn<StartCapture>(() => new Promise<Capture>(() => undefined));
  const onTurn = vi.fn();
  const { result } = renderHook(() => usePushToTalk({ t: 0, onTurn, start }));

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
  const { result } = renderHook(() => usePushToTalk({ t: 0, onTurn: vi.fn(), start: mic.start }));

  holdV();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(START_TIMEOUT_MS);
  });

  expect(result.current.error).toMatch(/^The microphone didn't start/);
  expect(mic.stop).toHaveBeenCalled();
});

test("a microphone that never stops times out with a message", async () => {
  vi.useFakeTimers();
  const stop = vi.fn(() => new Promise<Blob>(() => undefined));
  const start = vi.fn((onLive: () => void) => {
    queueMicrotask(onLive);
    return Promise.resolve<Capture>({ stop });
  });
  const onTurn = vi.fn();
  const { result } = renderHook(() => usePushToTalk({ t: 0, onTurn, start }));

  holdV();
  await settle();
  releaseV();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(STOP_TIMEOUT_MS);
  });

  expect(result.current.error).toMatch(/^The turn couldn't be recorded/);
  expect(onTurn).not.toHaveBeenCalled();
});

test("unmounting mid-turn closes the microphone", async () => {
  const mic = fakeMic();
  const onTurn = vi.fn();
  const { unmount } = renderHook(() => usePushToTalk({ t: 0, onTurn, start: mic.start }));

  holdV();
  await settle();
  unmount();
  await settle();

  expect(mic.stop).toHaveBeenCalled();
  expect(onTurn).not.toHaveBeenCalled();
});
