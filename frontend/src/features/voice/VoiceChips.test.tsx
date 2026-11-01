import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { VoiceChips, type HeardChip } from "./VoiceChips";

const chips: HeardChip[] = [
  { id: 1, phrase: "never drops it", value: "fail", quote: "it drops it here", t: 3.25 },
  { id: 2, phrase: "places it in the bowl", value: "pass", quote: "right in the bowl", t: 7 },
];

function renderChips() {
  const handlers = { onConfirm: vi.fn(), onDiscard: vi.fn(), onSeek: vi.fn() };
  render(<VoiceChips chips={chips} pending={false} {...handlers} />);
  return handlers;
}

test("each chip shows its Phrase, pass or fail, the quote and the moment", () => {
  renderChips();

  const chip = screen.getByRole("group", { name: "never drops it" });
  expect(chip).toHaveTextContent("never drops it");
  expect(chip).toHaveTextContent("Fail");
  expect(chip).toHaveTextContent("“it drops it here”");
  expect(within(chip).getByRole("button", { name: "Seek to 3.3 s" })).toBeInTheDocument();
});

test("the moment seeks the player", () => {
  const { onSeek } = renderChips();

  fireEvent.click(screen.getByRole("button", { name: "Seek to 7.0 s" }));

  expect(onSeek).toHaveBeenCalledWith(7);
});

test("Confirm and Discard act on their own chip", () => {
  const { onConfirm, onDiscard } = renderChips();
  const second = screen.getByRole("group", { name: "places it in the bowl" });

  fireEvent.click(within(second).getByRole("button", { name: "Confirm" }));
  fireEvent.click(
    within(screen.getByRole("group", { name: "never drops it" })).getByRole("button", {
      name: "Discard",
    }),
  );

  expect(onConfirm).toHaveBeenCalledWith(chips[1]);
  expect(onDiscard).toHaveBeenCalledWith(chips[0]);
});
