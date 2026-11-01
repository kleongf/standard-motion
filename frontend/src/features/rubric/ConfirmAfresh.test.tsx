import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { ConfirmAfresh } from "./ConfirmAfresh";

function renderOpen() {
  const onConfirm = vi.fn();
  const onOpenChange = vi.fn();
  render(<ConfirmAfresh open onOpenChange={onOpenChange} onConfirm={onConfirm} />);
  return { onConfirm, onOpenChange };
}

test("says what starting afresh loses", () => {
  renderOpen();

  const dialog = screen.getByRole("alertdialog", { name: "Start the draft afresh?" });
  expect(dialog).toHaveTextContent("edits on its Criterion cards");
  expect(dialog).toHaveTextContent("Rubric settings");
  expect(dialog).toHaveTextContent("interview");
});

test("starts afresh only when confirmed", () => {
  const { onConfirm, onOpenChange } = renderOpen();

  fireEvent.click(screen.getByRole("button", { name: "Keep the draft" }));
  expect(onConfirm).not.toHaveBeenCalled();
  expect(onOpenChange).toHaveBeenLastCalledWith(false);

  fireEvent.click(screen.getByRole("button", { name: "Start afresh" }));
  expect(onConfirm).toHaveBeenCalledOnce();
});
