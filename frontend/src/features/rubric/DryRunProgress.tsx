// The draft's dry run in the Describe page's top bar, while Spark is asking. Once it has finished
// the line goes: each visual Criterion card shows what it found, a pass rate or why it couldn't
// ask, and a finished run may be an older draft's.
import type { components } from "../../api/schema";
import { JobProgress } from "../jobs/JobProgress";
import { dryRunTitle } from "./dryRun";

type Job = components["schemas"]["Job"];

export function DryRunProgress(props: { job: Job | null | undefined }) {
  const { job } = props;
  if (!job || job.finished) return null;
  return (
    <p className="text-xs text-muted-foreground" data-testid="dry-run">
      · <JobProgress job={job} title={dryRunTitle(job.items)} compact />
    </p>
  );
}
