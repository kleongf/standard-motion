// The latest export: its progress, an Episode at a time, while it runs or if it failed; once it's
// written, what it holds and its folder, ready to copy.
import type { components } from "../../api/schema";
import { JobProgress } from "../jobs/JobProgress";
import { CopyPath } from "./CopyPath";
import type { PastExport } from "./useExport";

type Job = components["schemas"]["Job"];

const TITLE = { running: "Exporting", finished: "Last export" };

export function ExportStatus(props: {
  job: Job | null | undefined;
  latest: PastExport | undefined;
}) {
  const { job, latest } = props;
  if (!job) return null;
  if (!job.finished || job.failed > 0) return <JobProgress job={job} title={TITLE} />;
  const summary = job.items.find((item) => item.step === "export_finish")?.detail;
  return (
    <div className="grid gap-2 rounded-lg border p-4" data-testid="export-written">
      <div className="text-sm font-medium">Exported</div>
      {summary && <p className="text-sm text-muted-foreground">{summary}</p>}
      {latest && <CopyPath path={latest.path} />}
    </div>
  );
}
