import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import type { Episode } from "../episodes/useEpisodes";
import type { Playhead } from "../episodes/usePlayhead";
import { LabelPanel } from "./LabelPanel";

afterEach(() => {
  vi.unstubAllGlobals();
});

const EPISODE: Episode = {
  id: "droid_1.0.1:7",
  source: "droid_1.0.1",
  index: 7,
  instruction: null,
  dataset_outcome: null,
  reference_labelled: false,
  frames: 90,
  fps: 15,
  duration_s: 6,
  cameras: ["exterior_image_1_left"],
  task_object: "red mug",
  task_target: "shelf",
};

const PLAYHEAD: Playhead = {
  t: 0,
  playing: false,
  seekTarget: { t: 0 },
  seek: vi.fn(),
  toggle: vi.fn(),
  onTime: vi.fn(),
  onEnded: vi.fn(),
};

function renderPanel(episode: Episode) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(Response.json([]))),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <LabelPanel
        episode={episode}
        phrases={["never drops it"]}
        playhead={PLAYHEAD}
        relabel={false}
        onSaved={vi.fn()}
      />
    </QueryClientProvider>,
  );
}

test("an Episode with no instruction starts from the task the selection pass named, editable", () => {
  renderPanel(EPISODE);

  const field = screen.getByLabelText(/^Instruction/);
  expect(field).toHaveValue("Put the red mug in or on the shelf");

  fireEvent.change(field, { target: { value: "Put the red mug on the top shelf" } });
  expect(field).toHaveValue("Put the red mug on the top shelf");
});

test("without the selection pass's names the instruction starts empty", () => {
  renderPanel({ ...EPISODE, task_object: null, task_target: null });

  expect(screen.getByLabelText(/^Instruction/)).toHaveValue("");
  expect(screen.getByText("(none recorded)")).toBeInTheDocument();
});

test("an Episode with its own instruction asks for none", () => {
  renderPanel({ ...EPISODE, instruction: "Put the marker in the pot" });

  expect(screen.queryByLabelText(/^Instruction/)).not.toBeInTheDocument();
});
