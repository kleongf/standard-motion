import { Progress } from "@/components/ui/progress";

import type { components } from "../../api/schema";

type Job = components["schemas"]["Job"];
type JobItem = components["schemas"]["JobItem"];

const STEP_NAMES: Record<string, string> = {
  baseline: "Spark-alone baseline",
  track_wrist: "Wrist track",
};

function itemName(item: JobItem): string {
  const step = STEP_NAMES[item.step];
  return step ? `${item.label} · ${step}` : item.label;
}

/** What a job is called while it runs and once it has finished. */
export interface JobTitle {
  running: string;
  finished: string;
}

const INGEST: JobTitle = { running: "Ingesting", finished: "Last ingest" };

/** One quiet line, for a bar above other work: what runs, how far, how many failed; no detail. */
function CompactProgress(props: { job: Job; title: JobTitle }) {
  const { job, title } = props;
  const settled = job.done + job.failed;
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs text-muted-foreground tabular-nums"
      data-testid="job-progress"
    >
      {job.finished ? title.finished : title.running} · {settled} of {job.total}
      {job.failed > 0 && ` · ${String(job.failed)} failed`}
      <Progress value={(settled / job.total) * 100} className="h-1 w-12" />
    </span>
  );
}

export function JobProgress(props: { job: Job; title?: JobTitle; compact?: boolean }) {
  const { job, title = INGEST } = props;
  if (props.compact) return <CompactProgress job={job} title={title} />;
  const settled = job.done + job.failed;
  const failed = job.items.filter((item) => item.status === "failed");
  const running = job.items.filter((item) => item.status === "running");
  return (
    <div className="rounded-lg border p-4" data-testid="job-progress">
      <div className="flex items-baseline gap-2 text-sm">
        <span className="font-medium">{job.finished ? title.finished : title.running}</span>
        <span className="text-muted-foreground tabular-nums">
          {settled} of {job.total}
          {job.failed > 0 && ` · ${String(job.failed)} failed`}
        </span>
      </div>
      <Progress value={(settled / job.total) * 100} className="mt-2 h-1.5" />
      {running.length > 0 && (
        <p className="mt-2 text-xs text-muted-foreground">
          Now: {running.map(itemName).join(", ")}
        </p>
      )}
      {failed.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs">
          {failed.map((item) => (
            <li key={item.position}>
              <span className="font-medium text-destructive">{itemName(item)}</span>{" "}
              <span className="text-muted-foreground">{item.detail}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
