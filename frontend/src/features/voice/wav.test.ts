import { expect, test } from "vitest";

import { downsample, encodeWav, TARGET_RATE } from "./wav";

function text(view: DataView, at: number, length: number): string {
  return String.fromCharCode(...new Uint8Array(view.buffer, at, length));
}

test("encodes mono 16-bit PCM WAV at 16 kHz", async () => {
  const wav = encodeWav(new Float32Array([0, 1, -1, 0.5]));

  expect(wav.type).toBe("audio/wav");
  const view = new DataView(await wav.arrayBuffer());
  expect(view.byteLength).toBe(44 + 4 * 2);
  expect(text(view, 0, 4)).toBe("RIFF");
  expect(view.getUint32(4, true)).toBe(36 + 8);
  expect(text(view, 8, 8)).toBe("WAVEfmt ");
  expect(view.getUint16(20, true)).toBe(1); // PCM
  expect(view.getUint16(22, true)).toBe(1); // mono
  expect(view.getUint32(24, true)).toBe(16_000);
  expect(view.getUint32(28, true)).toBe(32_000); // bytes per second
  expect(view.getUint16(34, true)).toBe(16); // bits per sample
  expect(text(view, 36, 4)).toBe("data");
  expect(view.getUint32(40, true)).toBe(8);
  const samples = [0, 1, 2, 3].map((i) => view.getInt16(44 + i * 2, true));
  expect(samples).toEqual([0, 32767, -32768, 16383]); // 0.5 × 32767, truncated
});

test("clips samples outside -1 to 1", async () => {
  const view = new DataView(await encodeWav(new Float32Array([3, -3])).arrayBuffer());

  expect([view.getInt16(44, true), view.getInt16(46, true)]).toEqual([32767, -32768]);
});

test("downsamples 48 kHz to 16 kHz by averaging each three samples", () => {
  const input = new Float32Array([0.3, 0.3, 0.3, -0.6, 0, 0, 0.9, 0.9, 0.9]);

  const out = downsample(input, 48_000);

  expect(TARGET_RATE).toBe(16_000);
  expect(Array.from(out).map((x) => Number(x.toFixed(4)))).toEqual([0.3, -0.2, 0.9]);
});

test("downsamples a rate that isn't a multiple of 16 kHz to the right length", () => {
  const second = new Float32Array(44_100).fill(0.25);

  const out = downsample(second, 44_100);

  expect(out.length).toBe(16_000);
  expect(out.every((x) => Math.abs(x - 0.25) < 1e-6)).toBe(true);
});

test("leaves 16 kHz audio as it is", () => {
  const input = new Float32Array([0.1, 0.2]);

  expect(Array.from(downsample(input, 16_000))).toEqual(Array.from(input));
});
