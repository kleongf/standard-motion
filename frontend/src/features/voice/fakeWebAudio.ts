// Test helper: a fake microphone and Web Audio graph in place of the browser's (jsdom has
// neither), so `openMicrophone` runs for real. The test plays audio through it, chunk by chunk,
// and sees what was opened and closed.
import { vi } from "vitest";

export const RATE = 16_000;
const QUANTUM = 128;

class FakePort {
  onmessage: ((event: { data: unknown }) => void) | null = null;
  /** Off, the worklet holds flushes until `answer()`, as one busy rendering would. */
  answering = true;
  held: unknown[] = [];
  readonly close = vi.fn();

  postMessage(data: unknown) {
    if (this.answering) queueMicrotask(() => this.onmessage?.({ data }));
    else this.held.push(data);
  }

  answer() {
    this.held.splice(0).forEach((data) => this.onmessage?.({ data }));
  }
}

export function stubWebAudio() {
  const tracks: { stop: ReturnType<typeof vi.fn>; end: () => void }[] = [];
  const contexts: { close: ReturnType<typeof vi.fn> }[] = [];
  const ports: FakePort[] = [];

  const getUserMedia = vi.fn(() => {
    const ended: (() => void)[] = [];
    const track = {
      stop: vi.fn(),
      end: () => {
        ended.forEach((listener) => {
          listener();
        });
      },
      addEventListener: (_: "ended", listener: () => void) => ended.push(listener),
    };
    tracks.push(track);
    return Promise.resolve({ getTracks: () => [track] });
  });

  class FakeContext {
    sampleRate = RATE;
    state = "running";
    audioWorklet = { addModule: () => Promise.resolve() };
    resume = () => Promise.resolve();
    close = vi.fn(() => Promise.resolve());
    constructor() {
      contexts.push(this);
    }
    createMediaStreamSource() {
      return { connect: vi.fn(), disconnect: vi.fn() };
    }
  }

  class FakeNode {
    port = new FakePort();
    constructor() {
      ports.push(this.port);
    }
  }

  Object.defineProperty(navigator, "mediaDevices", {
    value: { getUserMedia },
    configurable: true,
  });
  vi.stubGlobal("AudioContext", FakeContext);
  vi.stubGlobal("AudioWorkletNode", FakeNode);
  URL.createObjectURL = () => "blob:worklet";

  return {
    getUserMedia,
    tracks,
    contexts,
    /** The open worklet's port (the latest opened). */
    port: () => {
      const port = ports.at(-1);
      if (!port) throw new Error("no microphone was opened");
      return port;
    },
    /** `seconds` of audio from the latest microphone, a render quantum at a time. */
    play(seconds: number, sample = 0.5) {
      const port = ports.at(-1);
      for (let n = 0; n < Math.round((seconds * RATE) / QUANTUM); n++) {
        port?.onmessage?.({ data: new Float32Array(QUANTUM).fill(sample) });
      }
    },
  };
}
