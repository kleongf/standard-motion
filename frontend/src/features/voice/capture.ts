// The microphone, open across push-to-talk turns: raw PCM through the Web Audio API (an
// AudioWorklet copies each render quantum out). It keeps the last PRE_ROLL_S of audio, so a turn
// starts just before the key went down, and each turn ends as a 16 kHz mono WAV.
import { downsample, encodeWav } from "./wav";

export interface Recording {
  wav: Blob;
  /** Seconds heard after the turn began: the pre-roll before it doesn't count. */
  heldS: number;
}

export interface Capture {
  /** End the turn: what was heard, as WAV. The microphone stays open. */
  stop: () => Promise<Recording>;
}

export interface Microphone {
  /** Begin a turn with the PRE_ROLL_S of audio just before it; `onLive` is called when audio
   * from after this call arrives, which is when the turn is really being heard. */
  record: (onLive: () => void) => Capture;
  /** Close the microphone and its audio graph. */
  close: () => Promise<void>;
}

/** Opens the microphone; `onEnded` is called if it closes on its own (unplugged, or the
 * permission taken back). */
export type OpenMicrophone = (onEnded: () => void) => Promise<Microphone>;

export const PRE_ROLL_S = 0.3;
const PROCESSOR = "winnow-capture";
// Every message to the worklet is a flush, which it answers with the same message. Messages on a
// port arrive in order, so the answer comes after every chunk rendered before it.
const WORKLET = `
class Capture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.port.onmessage = (event) => this.port.postMessage(event.data);
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

interface Flush {
  flush: number;
}

/** One turn's audio: the pre-roll, then what is heard after it began. */
interface Heard {
  chunks: Float32Array[];
  after: number; // samples heard since the turn began
  onLive: () => void;
}

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

/** The latest `size` samples (or up to one chunk more), as the chunks they came in. */
function recent(size: number) {
  const chunks: Float32Array[] = [];
  let length = 0;
  return {
    add(chunk: Float32Array) {
      chunks.push(chunk);
      length += chunk.length;
      while (chunks.length > 1 && length - (chunks[0]?.length ?? 0) >= size) {
        length -= chunks.shift()?.length ?? 0;
      }
    },
    copy: () => [...chunks],
  };
}

function hear(turn: Heard, chunk: Float32Array) {
  turn.chunks.push(chunk);
  turn.after += chunk.length;
  if (turn.after === chunk.length) turn.onLive();
}

async function closed(stream: MediaStream, context: AudioContext): Promise<void> {
  stream.getTracks().forEach((track) => {
    track.stop();
  });
  await context.close();
}

async function graph(stream: MediaStream) {
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
  return { context, source, node };
}

export const openMicrophone: OpenMicrophone = async (onEnded) => {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });
  const { context, source, node } = await graph(stream);
  const rate = context.sampleRate;
  const preRoll = recent(Math.round(PRE_ROLL_S * rate));
  const turns = new Set<Heard>();
  const flushes = new Map<number, () => void>();
  let flushesSent = 0;
  let open = true;

  node.port.onmessage = (event: MessageEvent<Float32Array | Flush>) => {
    const data = event.data;
    if (!(data instanceof Float32Array)) {
      flushes.get(data.flush)?.();
      return;
    }
    preRoll.add(data);
    turns.forEach((turn) => {
      hear(turn, data);
    });
  };

  /** Resolves once every chunk rendered before it has arrived. */
  const flush = () =>
    new Promise<void>((resolve) => {
      const id = flushesSent++;
      const done = () => {
        flushes.delete(id);
        resolve();
      };
      flushes.set(id, done);
      setTimeout(done, FLUSH_TIMEOUT_MS);
      node.port.postMessage({ flush: id } satisfies Flush);
    });

  const close = async () => {
    if (!open) return;
    open = false;
    flushes.forEach((done) => {
      done();
    });
    source.disconnect();
    node.port.close();
    await closed(stream, context);
  };

  stream.getTracks().forEach((track) => {
    track.addEventListener("ended", () => {
      void close().finally(onEnded);
    });
  });
  source.connect(node);
  return {
    record: (onLive) => {
      if (!open) throw new Error("the microphone is closed");
      if (context.state === "suspended") context.resume().catch(() => undefined);
      const turn: Heard = { chunks: preRoll.copy(), after: 0, onLive };
      turns.add(turn);
      return {
        stop: async () => {
          await flush(); // chunks may still be on their way
          turns.delete(turn);
          return {
            wav: encodeWav(downsample(joined(turn.chunks), rate)),
            heldS: turn.after / rate,
          };
        },
      };
    },
    close,
  };
};
