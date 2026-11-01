// What Muse Voice Transcribe takes: WAV, mono 16-bit PCM at 16 kHz. The microphone runs at the
// audio device's rate (often 44.1 or 48 kHz), so each turn is downsampled and encoded here.

export const TARGET_RATE = 16_000;
const HEADER_BYTES = 44;

/** Mono samples at `fromRate`, as 16 kHz: each output sample averages the input samples it
 * spans, which also filters what 16 kHz can't hold. */
export function downsample(samples: Float32Array, fromRate: number): Float32Array {
  if (fromRate === TARGET_RATE) return samples.slice();
  const ratio = fromRate / TARGET_RATE;
  const out = new Float32Array(Math.floor(samples.length / ratio));
  for (let i = 0; i < out.length; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.max(start + 1, Math.floor((i + 1) * ratio));
    let sum = 0;
    for (let j = start; j < end; j++) sum += samples[j] ?? 0;
    out[i] = sum / (end - start);
  }
  return out;
}

/** 16 kHz mono samples in -1 to 1 (louder ones are clipped) as a 16-bit PCM WAV file. */
export function encodeWav(samples: Float32Array): Blob {
  const view = new DataView(new ArrayBuffer(HEADER_BYTES + samples.length * 2));
  const ascii = (at: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(at + i, s.charCodeAt(i));
  };
  ascii(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  ascii(8, "WAVEfmt ");
  view.setUint32(16, 16, true); // fmt chunk size
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, TARGET_RATE, true);
  view.setUint32(28, TARGET_RATE * 2, true); // bytes per second
  view.setUint16(32, 2, true); // bytes per frame
  view.setUint16(34, 16, true); // bits per sample
  ascii(36, "data");
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((sample, i) => {
    const clipped = Math.max(-1, Math.min(1, sample));
    view.setInt16(HEADER_BYTES + i * 2, clipped < 0 ? clipped * 0x8000 : clipped * 0x7fff, true);
  });
  return new Blob([view.buffer], { type: "audio/wav" });
}
