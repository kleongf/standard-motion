import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import type { components } from "../../api/schema";
import { DryRunProgress } from "./DryRunProgress";

type Job = components["schemas"]["Job"];
type JobItem = components["schemas"]["JobItem"];

function item(position: number, status: JobItem["status"], detail: string | null = null): JobItem {
  const step = position % 2 === 0 ? "crop" : "visual";
  return { position, step, label: "droid_100:6 ask-video", status, detail };
}

function job(items: JobItem[]): Job {
  const count = (status: JobItem["status"]) => items.filter((i) => i.status === status).length;
  return {
    id: 1,
    kind: "visual-dry-run",
    created_at: "2026-10-31T00:00:00Z",
    total: items.length,
    queued: count("queued"),
    running: count("running"),
    done: count("done"),
    failed: count("failed"),
    finished: count("queued") + count("running") === 0,
    items,
  };
}

test("says what Spark is asking while the dry run runs", () => {
  render(<DryRunProgress job={job([item(0, "done"), item(1, "running")])} />);

  expect(screen.getByTestId("dry-run")).toHaveTextContent(
    "Asking 1 visual Criterion on the anchor pool · 1 of 2",
  );
});

test("counts a failed ask quietly, with no error", () => {
  render(
    <DryRunProgress job={job([item(0, "failed", "Over the Meta budget"), item(1, "queued")])} />,
  );

  const line = screen.getByTestId("dry-run");
  expect(line).toHaveTextContent("1 of 2 · 1 failed");
  expect(line).not.toHaveTextContent("Over the Meta budget");
});

test("is gone once the dry run has finished: the Criterion cards show what it found", () => {
  const { container } = render(<DryRunProgress job={job([item(0, "done"), item(1, "done")])} />);

  expect(container).toBeEmptyDOMElement();
});
