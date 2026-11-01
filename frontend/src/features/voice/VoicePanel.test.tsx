import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import type { Playhead } from "../episodes/usePlayhead";
import type { Capture, StartCapture } from "./capture";
import type { VoiceTurn } from "./useVoice";
import { VoicePanel } from "./VoicePanel";

const SECOND = new Blob([new Uint8Array(44 + 32_000)], { type: "audio/wav" });
const NEVER_DROPS = "never drops it";
const PLACES = "places it in the bowl";

const playhead: Playhead = {
  t: 1,
  playing: true,
  seekTarget: { t: 0 },
  seek: vi.fn(),
  toggle: vi.fn(),
  onTime: vi.fn(),
  onEnded: vi.fn(),
};

const mic: StartCapture = (onLive) => {
  queueMicrotask(onLive);
  return Promise.resolve<Capture>({ stop: () => Promise.resolve(SECOND) });
};

/** The backend: Meta is available or not, and each voice turn answers when the test says. */
function stubBackend(options: { metaAvailable?: boolean } = {}) {
  const turns: ((answer: VoiceTurn) => void)[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((request: Request) => {
      if (request.url.endsWith("/api/health")) {
        const available = options.metaAvailable ?? true;
        return Promise.resolve(
          Response.json({
            status: "ok",
            meta_api_key_configured: false,
            meta_available: available,
          }),
        );
      }
      return new Promise<Response>((resolve) => {
        turns.push((answer) => {
          resolve(Response.json(answer));
        });
      });
    }),
  );
  return turns;
}

function renderPanel(onConfirm: () => Promise<unknown> = () => Promise.resolve()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <VoicePanel
        episodeId="droid_100:1"
        unsure={[NEVER_DROPS, PLACES]}
        playhead={playhead}
        saving={false}
        onConfirm={onConfirm}
        start={mic}
      />
    </QueryClientProvider>,
  );
}

async function speak() {
  const voice = await screen.findByRole("region", { name: "Voice" });
  fireEvent.keyDown(globalThis.window, { key: "v", code: "KeyV" });
  await within(voice).findByRole("button", { name: /Listening/ });
  fireEvent.keyUp(globalThis.window, { key: "v", code: "KeyV" });
}

function heard(phrase: string, value: "pass" | "fail"): VoiceTurn {
  return { transcript: `about ${phrase}`, t: 1, chips: [{ phrase, value, quote: phrase }] };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

test("two quick turns both add their chips, whichever is heard first", async () => {
  const turns = stubBackend();
  renderPanel();

  await speak();
  await speak();
  await waitFor(() => {
    expect(turns).toHaveLength(2);
  });
  await act(async () => {
    turns[1]?.(heard(PLACES, "pass"));
    turns[0]?.(heard(NEVER_DROPS, "fail"));
    await Promise.resolve();
  });

  expect(await screen.findByRole("group", { name: NEVER_DROPS })).toHaveTextContent("Fail");
  expect(await screen.findByRole("group", { name: PLACES })).toHaveTextContent("Pass");
});

test("a confirmed chip leaves once its label is saved", async () => {
  const turns = stubBackend();
  let saved: () => void = () => undefined;
  const onConfirm = vi.fn(
    () =>
      new Promise<void>((resolve) => {
        saved = resolve;
      }),
  );
  renderPanel(onConfirm);
  await speak();
  await waitFor(() => {
    expect(turns).toHaveLength(1);
  });
  act(() => {
    turns[0]?.(heard(NEVER_DROPS, "fail"));
  });
  const chip = await screen.findByRole("group", { name: NEVER_DROPS });

  fireEvent.click(within(chip).getByRole("button", { name: "Confirm" }));
  expect(onConfirm).toHaveBeenCalledWith(NEVER_DROPS, "fail");
  expect(chip).toBeInTheDocument(); // still saving

  await act(async () => {
    saved();
    await Promise.resolve();
  });
  await waitFor(() => {
    expect(screen.queryByRole("group", { name: NEVER_DROPS })).not.toBeInTheDocument();
  });
});

test("a chip whose label fails to save stays, to confirm again", async () => {
  const turns = stubBackend();
  const onConfirm = vi.fn(() => Promise.reject(new Error("The label couldn't be saved")));
  renderPanel(onConfirm);
  await speak();
  await waitFor(() => {
    expect(turns).toHaveLength(1);
  });
  act(() => {
    turns[0]?.(heard(NEVER_DROPS, "fail"));
  });
  const chip = await screen.findByRole("group", { name: NEVER_DROPS });

  fireEvent.click(within(chip).getByRole("button", { name: "Confirm" }));
  await act(async () => {
    await Promise.resolve();
  });

  expect(onConfirm).toHaveBeenCalled();
  expect(screen.getByRole("group", { name: NEVER_DROPS })).toBeInTheDocument();
});

test("a turn too short to hear says so in an alert", async () => {
  stubBackend();
  renderPanel();
  const voice = await screen.findByRole("region", { name: "Voice" });

  fireEvent.keyDown(globalThis.window, { key: "v", code: "KeyV" });
  fireEvent.keyUp(globalThis.window, { key: "v", code: "KeyV" }); // before the mic is live

  expect(await within(voice).findByRole("alert")).toHaveTextContent(
    "Too short to hear: hold V while you talk",
  );
});

test("without the Meta API there is no Voice panel, and V opens no microphone", async () => {
  stubBackend({ metaAvailable: false });
  const start = vi.fn(mic);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <VoicePanel
        episodeId="droid_100:1"
        unsure={[NEVER_DROPS]}
        playhead={playhead}
        saving={false}
        onConfirm={() => Promise.resolve()}
        start={start}
      />
    </QueryClientProvider>,
  );
  await waitFor(() => {
    expect(globalThis.fetch).toHaveBeenCalled();
  });
  await act(async () => {
    await Promise.resolve();
  });

  fireEvent.keyDown(globalThis.window, { key: "v", code: "KeyV" });

  expect(screen.queryByRole("region", { name: "Voice" })).not.toBeInTheDocument();
  expect(start).not.toHaveBeenCalled();
});
