import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import type { ReviewItem } from "./useReview";
import { YourCall } from "./YourCall";

const item: ReviewItem = {
  episode_id: "droid_100:1",
  confidence: 0.62,
  reason: "Needs review: …",
  unsure: [
    { phrase: "places it in the bowl", signals: ["near threshold (4.4 cm against ≤ 5 cm)"] },
    { phrase: "never drops it", signals: ["track lost (wrist)"] },
  ],
};

test("lists only the unsure Phrases with their signals", () => {
  render(<YourCall item={item} pending={false} onAnswer={vi.fn()} />);

  const phrases = screen.getAllByRole("group");
  expect(phrases.map((p) => p.getAttribute("aria-label"))).toEqual([
    "places it in the bowl",
    "never drops it",
  ]);
  expect(phrases[0]).toHaveTextContent("near threshold (4.4 cm against ≤ 5 cm)");
});

test("keys 1 and 2 answer the focused Phrase, the first until another is focused", () => {
  const onAnswer = vi.fn();
  render(<YourCall item={item} pending={false} onAnswer={onAnswer} />);

  fireEvent.keyDown(globalThis.window, { key: "1" });
  expect(onAnswer).toHaveBeenLastCalledWith("places it in the bowl", "pass");

  fireEvent.click(screen.getByRole("group", { name: "never drops it" }));
  fireEvent.keyDown(globalThis.window, { key: "2" });
  expect(onAnswer).toHaveBeenLastCalledWith("never drops it", "fail");
});

test("arrow keys move the focus between Phrases, stopping at either end", () => {
  const onAnswer = vi.fn();
  render(<YourCall item={item} pending={false} onAnswer={onAnswer} />);

  fireEvent.keyDown(globalThis.window, { key: "ArrowDown" });
  fireEvent.keyDown(globalThis.window, { key: "ArrowDown" });
  fireEvent.keyDown(globalThis.window, { key: "1" });
  expect(onAnswer).toHaveBeenLastCalledWith("never drops it", "pass");

  fireEvent.keyDown(globalThis.window, { key: "ArrowUp" });
  fireEvent.keyDown(globalThis.window, { key: "ArrowUp" });
  fireEvent.keyDown(globalThis.window, { key: "2" });
  expect(onAnswer).toHaveBeenLastCalledWith("places it in the bowl", "fail");
});

test("the buttons answer their own Phrase", () => {
  const onAnswer = vi.fn();
  render(<YourCall item={item} pending={false} onAnswer={onAnswer} />);

  const second = screen.getByRole("group", { name: "never drops it" });
  fireEvent.click(within(second).getByRole("button", { name: /Pass/ }));

  expect(onAnswer).toHaveBeenLastCalledWith("never drops it", "pass");
});

test("keys do nothing while an answer is saving or while typing", () => {
  const onAnswer = vi.fn();
  const { rerender } = render(<YourCall item={item} pending onAnswer={onAnswer} />);
  fireEvent.keyDown(globalThis.window, { key: "1" });

  rerender(
    <>
      <input aria-label="Note" />
      <YourCall item={item} pending={false} onAnswer={onAnswer} />
    </>,
  );
  fireEvent.keyDown(screen.getByLabelText("Note"), { key: "2" });

  expect(onAnswer).not.toHaveBeenCalled();
});
