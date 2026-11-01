import { afterEach, expect, test, vi } from "vitest";

import { openMicrophone, PRE_ROLL_S } from "./capture";
import { RATE, stubWebAudio } from "./fakeWebAudio";

const QUANTUM = 128;
// Whole render quanta at 16 kHz.
const HALF = (64 * QUANTUM) / RATE;
const QUARTER = (32 * QUANTUM) / RATE;

/** Samples in a 16 kHz WAV. */
const samples = (wav: Blob) => (wav.size - 44) / 2;

afterEach(() => {
  vi.unstubAllGlobals();
});

test("a turn starts with the audio from just before it, which isn't counted as held", async () => {
  const audio = stubWebAudio();
  const mic = await openMicrophone(vi.fn());
  audio.play(1); // the microphone is open, between turns

  const turn = mic.record(vi.fn());
  audio.play(HALF);
  const heard = await turn.stop();

  expect(heard.heldS).toBe(HALF);
  const preRoll = samples(heard.wav) - HALF * RATE;
  expect(preRoll).toBeGreaterThanOrEqual(PRE_ROLL_S * RATE);
  expect(preRoll).toBeLessThan(PRE_ROLL_S * RATE + QUANTUM);
});

test("a turn is live with the first audio after it began", async () => {
  const audio = stubWebAudio();
  const mic = await openMicrophone(vi.fn());
  audio.play(1);
  const onLive = vi.fn();

  mic.record(onLive);
  expect(onLive).not.toHaveBeenCalled(); // the pre-roll doesn't count
  audio.play(0.1);

  expect(onLive).toHaveBeenCalledOnce();
});

test("stopping waits for the worklet's flush, and keeps the audio that came before it", async () => {
  const audio = stubWebAudio();
  const mic = await openMicrophone(vi.fn());
  const turn = mic.record(vi.fn());
  audio.play(HALF);
  audio.port().answering = false;

  let done = false;
  const stopped = turn.stop().then((heard) => {
    done = true;
    return heard;
  });
  audio.play(QUARTER); // rendered before the flush, still on its way
  await Promise.resolve();
  expect(done).toBe(false);
  audio.port().answer();

  expect((await stopped).heldS).toBe(HALF + QUARTER);
});

test("ending a turn leaves the microphone open for the next", async () => {
  const audio = stubWebAudio();
  const mic = await openMicrophone(vi.fn());
  await mic.record(vi.fn()).stop();

  const next = mic.record(vi.fn());
  audio.play(HALF);

  expect((await next.stop()).heldS).toBe(HALF);
  expect(audio.getUserMedia).toHaveBeenCalledOnce();
  expect(audio.tracks[0]?.stop).not.toHaveBeenCalled();
});

test("closing stops the microphone and the audio graph, and records no more", async () => {
  const audio = stubWebAudio();
  const mic = await openMicrophone(vi.fn());

  await mic.close();

  expect(audio.tracks[0]?.stop).toHaveBeenCalled();
  expect(audio.contexts[0]?.close).toHaveBeenCalled();
  expect(audio.port().close).toHaveBeenCalled();
  expect(() => mic.record(vi.fn())).toThrow("the microphone is closed");
});

test("a microphone that ends on its own closes and says so", async () => {
  const audio = stubWebAudio();
  const onEnded = vi.fn();
  await openMicrophone(onEnded);

  audio.tracks[0]?.end();
  await vi.waitFor(() => {
    expect(onEnded).toHaveBeenCalled();
  });
  expect(audio.contexts[0]?.close).toHaveBeenCalled();
});
