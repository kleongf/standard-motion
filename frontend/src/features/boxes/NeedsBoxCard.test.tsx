import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import type { Episode } from "../episodes/useEpisodes";
import { NeedsBoxCard } from "./NeedsBoxCard";

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

function card(episode: Episode) {
  const onOpen = vi.fn();
  render(<NeedsBoxCard episode={episode} onOpen={onOpen} />);
  return { onOpen, button: screen.getByRole("button", { name: "Draw a box for Episode 7" }) };
}

test("names the object to box, and that the dataset gave no instruction", () => {
  const { button, onOpen } = card(EPISODE);

  expect(button).toHaveTextContent("Box: red mug");
  expect(button).toHaveTextContent("No instruction in the dataset");
  fireEvent.click(button);
  expect(onOpen).toHaveBeenCalledOnce();
});

test("shows the instruction, and no object hint where the selection pass named none", () => {
  const { button } = card({
    ...EPISODE,
    instruction: "Put the marker in the pot",
    task_object: null,
  });

  expect(button).toHaveTextContent("Put the marker in the pot");
  expect(button).not.toHaveTextContent("Box:");
  expect(button).not.toHaveTextContent("No instruction");
});
