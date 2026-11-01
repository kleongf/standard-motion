import { describe, expect, it } from "vitest";

import type { components } from "../../api/schema";
import { dryRunTitle } from "./dryRun";

type JobItem = components["schemas"]["JobItem"];

/** A crop, then a visual item, per anchor Episode and visual Criterion, as the dry run queues. */
function asks(pairs: [string, string][]): JobItem[] {
  return pairs.flatMap(([episode, criterion], i) =>
    ["crop", "visual"].map((step, j) => ({
      position: 2 * i + j,
      step,
      label: `${episode} ${criterion}`,
      status: "queued" as const,
      detail: null,
    })),
  );
}

describe("dryRunTitle", () => {
  it("counts each visual Criterion once, however many anchor Episodes it is asked of", () => {
    const items = asks([
      ["droid_100:6", "in-bowl"],
      ["droid_100:7", "in-bowl"],
      ["droid_100:6", "upright"],
    ]);
    expect(dryRunTitle(items).running).toBe("Asking 2 visual Criteria on the anchor pool");
  });

  it("speaks of one Criterion in the singular", () => {
    const items = asks([["droid_100:6", "ask-video"]]);
    expect(dryRunTitle(items).running).toBe("Asking 1 visual Criterion on the anchor pool");
  });
});
