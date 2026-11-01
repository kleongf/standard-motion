// The Dataset outcome ("was the task done") against the Reference labels ("does it meet the
// Description"), the Episodes where they disagree, and the FailBench "did it succeed?" check
// scored against the Dataset outcome.
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { SectionHeading } from "../core/PageHeader";
import { Rate } from "./Rate";
import { balancedAccuracyText } from "./reportText";
import type { DatasetOutcome, FailBenchCheck } from "./useEvaluation";

function CrossTable(props: { outcome: DatasetOutcome }) {
  const o = props.outcome;
  return (
    <Table className="mt-2 max-w-md" aria-label="Dataset outcome against Reference labels">
      <TableHeader>
        <TableRow>
          <TableHead>Dataset outcome</TableHead>
          <TableHead className="text-right">Meets the Description</TableHead>
          <TableHead className="text-right">Fails it</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell className="font-medium">Success</TableCell>
          <TableCell className="text-right tabular-nums">{o.success_meets}</TableCell>
          <TableCell className="text-right tabular-nums">{o.success_fails}</TableCell>
        </TableRow>
        <TableRow>
          <TableCell className="font-medium">Failure</TableCell>
          <TableCell className="text-right tabular-nums">{o.failure_meets}</TableCell>
          <TableCell className="text-right tabular-nums">{o.failure_fails}</TableCell>
        </TableRow>
      </TableBody>
    </Table>
  );
}

function Disagreements(props: { outcome: DatasetOutcome }) {
  const rows = props.outcome.disagreements;
  if (rows.length === 0) {
    return (
      <p className="mt-2 text-xs text-muted-foreground">
        No labelled Episode&apos;s Dataset outcome disagrees with its Reference label.
      </p>
    );
  }
  return (
    <Table className="mt-2" aria-label="Dataset outcome disagreements">
      <TableHeader>
        <TableRow>
          <TableHead>Episode</TableHead>
          <TableHead>Dataset outcome</TableHead>
          <TableHead>Reference label</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((d) => (
          <TableRow key={d.episode_id}>
            <TableCell className="font-medium tabular-nums">{d.episode_id}</TableCell>
            <TableCell>{d.dataset_outcome ? "Success" : "Failure"}</TableCell>
            <TableCell className="whitespace-normal">
              {d.failed_phrases.length > 0
                ? `Fails ${d.failed_phrases.map((p) => `“${p}”`).join(", ")}`
                : "Meets the Description"}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function FailBench(props: { check: FailBenchCheck }) {
  const c = props.check;
  return (
    <div data-testid="failbench">
      <SectionHeading
        level={3}
        title="FailBench check"
        meta={`${String(c.answered)} Episodes`}
        info={
          <>
            Spark&apos;s plain &ldquo;did it succeed?&rdquo; answer on {c.answered} Episodes, scored
            against the Dataset outcome. FailBench reports 0.72 balanced accuracy on DROID.
          </>
        }
      />
      <dl className="mt-2 flex gap-8 text-sm">
        <div>
          <dt className="text-xs text-muted-foreground">Agrees with the Dataset outcome</dt>
          <dd>
            <Rate p={c.agrees} />
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Failures caught</dt>
          <dd>
            <Rate p={c.failures_caught} />
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Balanced accuracy</dt>
          <dd className="tabular-nums">{balancedAccuracyText(c.balanced_accuracy)}</dd>
        </div>
      </dl>
    </div>
  );
}

export function DatasetOutcomeSection(props: {
  outcome: DatasetOutcome;
  failbench: FailBenchCheck;
}) {
  const { outcome } = props;
  return (
    <div className="mt-8 grid gap-8 lg:grid-cols-2">
      <div data-testid="dataset-outcome">
        <SectionHeading
          level={3}
          title="Dataset outcome against Reference labels"
          meta={`${String(outcome.compared)} labelled${outcome.no_outcome > 0 ? ` · ${String(outcome.no_outcome)} ship no outcome` : ""}`}
          info="The Dataset outcome says whether the task was done, not whether the Episode meets the Description."
        />
        <CrossTable outcome={outcome} />
        <Disagreements outcome={outcome} />
      </div>
      <FailBench check={props.failbench} />
    </div>
  );
}
