import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { ConfirmExport } from "./ConfirmExport";

function renderOpen(unlabelled: number) {
  const onConfirm = vi.fn();
  const onOpenChange = vi.fn();
  render(
    <ConfirmExport
      open
      unlabelled={unlabelled}
      onOpenChange={onOpenChange}
      onConfirm={onConfirm}
    />,
  );
  return { onConfirm, onOpenChange };
}

test("warns how many Episodes aren't Reference-labelled yet", () => {
  renderOpen(3);

  const dialog = screen.getByRole("alertdialog", { name: "Export before labelling?" });
  expect(dialog).toHaveTextContent(
    "3 Episodes aren’t Reference-labelled yet. Exporting shows their decisions; label them first if you want them blind.",
  );
});

test("speaks of one Episode in the singular", () => {
  renderOpen(1);

  expect(screen.getByRole("alertdialog")).toHaveTextContent(
    "1 Episode isn’t Reference-labelled yet. Exporting shows its decision; label it first if you want it blind.",
  );
});

test("warns and never blocks: exporting anyway goes ahead", () => {
  const { onConfirm, onOpenChange } = renderOpen(2);

  fireEvent.click(screen.getByRole("button", { name: "Not yet" }));
  expect(onConfirm).not.toHaveBeenCalled();
  expect(onOpenChange).toHaveBeenLastCalledWith(false);

  fireEvent.click(screen.getByRole("button", { name: "Export anyway" }));
  expect(onConfirm).toHaveBeenCalledOnce();
});
