// The draft's dry run: Spark asked, in the background, the draft's visual Criteria it hasn't
// answered on the anchor pool, so their pass rates show before Run.
import type { components } from "../../api/schema";
import type { JobTitle } from "../jobs/JobProgress";

type JobItem = components["schemas"]["JobItem"];

/** The job kind the backend queues the dry run under (`visual.service.DRY_RUN`). */
export const DRY_RUN = "visual-dry-run";

/** Each item is labelled "{Episode id} {Criterion id}", and a Criterion id is a slug with no
 * space: the Criteria asked are the distinct last words. */
function criteriaAsked(items: JobItem[]): number {
  return new Set(items.map((item) => item.label.slice(item.label.lastIndexOf(" ") + 1))).size;
}

export function dryRunTitle(items: JobItem[]): JobTitle {
  const n = criteriaAsked(items);
  const criteria = `${String(n)} visual ${n === 1 ? "Criterion" : "Criteria"}`;
  return {
    running: `Asking ${criteria} on the anchor pool`,
    finished: `Asked ${criteria} on the anchor pool`,
  };
}
