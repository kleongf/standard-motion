import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import type { Episode } from "../episodes/useEpisodes";
import { BoxDialog } from "./BoxDialog";

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
  cameras: ["exterior_image_1_left", "exterior_image_2_left"],
  task_object: "red mug",
  task_target: "shelf",
};

function dialog(episode: Episode) {
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <BoxDialog queue={[episode]} onClose={() => undefined} />
    </QueryClientProvider>,
  );
}

test("loops the chosen view's clip beside frame 0, and follows the view", () => {
  dialog(EPISODE);
  const clip = screen.getByLabelText("Episode clip");
  expect(clip).toHaveAttribute("src", "/api/episodes/droid_1.0.1%3A7/clips/exterior_image_1_left");
  expect(clip).toHaveAttribute("loop");

  fireEvent.keyDown(globalThis.window, { key: "2" });
  expect(screen.getByLabelText("Episode clip")).toHaveAttribute(
    "src",
    "/api/episodes/droid_1.0.1%3A7/clips/exterior_image_2_left",
  );
});

test("names the object to box when the selection pass named one", () => {
  dialog(EPISODE);
  expect(screen.getByText("red mug")).toBeInTheDocument();
});
