import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { AuditCall } from "./AuditCall";
import type { AuditItem } from "./useAudit";

const PHRASES = ["grasps it on the first try", "never drops it"];
const item: AuditItem = {
  episode_id: "droid_100:0",
  kind: "keep",
  decision: "keep",
  reason: "Kept: every hard Phrase passes.",
  mark: null,
  failed: [],
};

function renderCall(shown: AuditItem = item) {
  const onGood = vi.fn();
  const onBad = vi.fn();
  render(
    <AuditCall item={shown} phrases={PHRASES} pending={false} onGood={onGood} onBad={onBad} />,
  );
  return { onGood, onBad };
}

test("Good marks the Episode at once", () => {
  const { onGood, onBad } = renderCall();

  fireEvent.click(screen.getByRole("button", { name: "Good" }));

  expect(onGood).toHaveBeenCalledOnce();
  expect(onBad).not.toHaveBeenCalled();
});

test("Bad asks which Phrase fails, and marks that one", () => {
  const { onBad } = renderCall();

  fireEvent.click(screen.getByRole("button", { name: "Bad…" }));
  fireEvent.click(screen.getByRole("button", { name: "“never drops it”" }));

  expect(onBad).toHaveBeenCalledWith("never drops it");
  expect(screen.getByRole("button", { name: "Good" })).toBeInTheDocument();
});

test("Cancel leaves the Phrase picker without marking", () => {
  const { onBad } = renderCall();

  fireEvent.click(screen.getByRole("button", { name: "Bad…" }));
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

  expect(onBad).not.toHaveBeenCalled();
  expect(screen.queryByRole("list", { name: "Failing Phrase" })).not.toBeInTheDocument();
});

test("shows the mark already given, naming the failing Phrase", () => {
  renderCall({ ...item, mark: "bad", failed: ["never drops it"] });

  expect(screen.getByTestId("audit-mark")).toHaveTextContent("Marked Bad: “never drops it”");
});

test("an item whose Triage decision changed says its mark isn't counted", () => {
  renderCall({ ...item, decision: "reject" });

  expect(screen.getByTestId("audit-moved")).toHaveTextContent(
    "Its Triage decision is now Reject, so its mark isn’t counted.",
  );
});

test("an item still decided as drawn says nothing more", () => {
  renderCall();

  expect(screen.queryByTestId("audit-moved")).toBeNull();
});
