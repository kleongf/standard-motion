// The microphone, open for one push-to-talk turn: raw PCM through the Web Audio API (an
// AudioWorklet copies each render quantum out), then a 16 kHz mono WAV when the turn ends.
import { downsample, encodeWav } from "./wav";

export interface Capture {
  /** Close the microphone; the turn as WAV. */
  stop: () => Promise<Blob>;
}

/** Opens the microphone; `onLive` is called when its first audio arrives, which is when the
 * turn is really being heard. */
export type StartCapture = (onLive: () => void) => Promise<Capture>;

const PROCESSOR = "winnow-capture";
const FLUSH = "flush";
// Messages on a port arrive in order, so the reply to "flush" comes after every chunk before it.
const WORKLET = `
class Capture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.port.onmessage = () => this.port.postMessage("${FLUSH}");
  }
  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel) this.port.postMessage(channel.slice());
    return true;
  }
}
registerProcessor("${PROCESSOR}", Capture);
`;
const FLUSH_TIMEOUT_MS = 1000; // past it, the turn is what arrived

let workletUrl: string | undefined;

function worklet(): string {
  workletUrl ??= URL.createObjectURL(new Blob([WORKLET], { type: "text/javascript" }));
  return workletUrl;
}

function joined(chunks: Float32Array[]): Float32Array {
  const out = new Float32Array(chunks.reduce((n, c) => n + c.length, 0));
  let at = 0;
  for (const chunk of chunks) {
    out.set(chunk, at);
    at += chunk.length;
  }
  return out;
}

async function closed(stream: MediaStream, context: AudioContext): Promise<void> {
  stream.getTracks().forEach((track) => {
    track.stop();
  });
  await context.close();
}

export const startCapture: StartCapture = async (onLive) => {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });
  const context = new AudioContext();
  try {
    await context.audioWorklet.addModule(worklet());
    // A context made outside a click or key press may start suspended, and renders nothing.
    await context.resume();
  } catch (error) {
    await closed(stream, context);
    throw error;
  }
  const source = context.createMediaStreamSource(stream);
  // No outputs: a sink, which the graph still renders.
  const node = new AudioWorkletNode(context, PROCESSOR, { numberOfOutputs: 0 });
  const chunks: Float32Array[] = [];
  let flushed: () => void = () => undefined;
  node.port.onmessage = (event: MessageEvent<Float32Array | typeof FLUSH>) => {
    if (event.data === FLUSH) {
      flushed();
      return;
    }
    chunks.push(event.data);
    if (chunks.length === 1) onLive();
  };
  source.connect(node);
  return {
    stop: async () => {
      source.disconnect(); // nothing new is captured, but chunks may still be on their way
      await new Promise<void>((resolve) => {
        flushed = resolve;
        setTimeout(resolve, FLUSH_TIMEOUT_MS);
        node.port.postMessage(FLUSH);
      });
      node.port.close();
      const rate = context.sampleRate;
      await closed(stream, context);
      return encodeWav(downsample(joined(chunks), rate));
    },
  };
};
