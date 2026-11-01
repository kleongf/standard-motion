// The Test run log: every Test set run, dated, with its Rubric version. Append-only, so the
// reported numbers are provably the last run before the freeze. A row opens its report.
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { countOf } from "./reportText";
import { useTestRuns, type SystemRow, type TestRun } from "./useEvaluation";

const RUN_FORMAT = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

function falseKeeps(run: TestRun, system: SystemRow["system"]): string {
  const row = run.report.comparison.rows.find((r) => r.system === system);
  return row ? countOf(row.false_keeps) : "";
}

export function TestRunLog(props: { shownId: number | null; onShow: (run: TestRun) => void }) {
  const runs = useTestRuns().data;
  if (!runs) return null;
  if (runs.length === 0) {
    return <p className="mt-2 text-sm text-muted-foreground">No Test set run yet.</p>;
  }
  return (
    <Table className="mt-2" aria-label="Test run log">
      <TableHeader>
        <TableRow>
          <TableHead>Run</TableHead>
          <TableHead className="text-right">Rubric</TableHead>
          <TableHead className="text-right">Labelled</TableHead>
          <TableHead>Winnow false keeps</TableHead>
          <TableHead>Spark alone false keeps</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run) => (
          <TableRow
            key={run.id}
            className="cursor-pointer"
            data-state={run.id === props.shownId ? "selected" : undefined}
            onClick={() => {
              props.onShow(run);
            }}
          >
            <TableCell className="tabular-nums">
              {RUN_FORMAT.format(new Date(run.run_at))}
            </TableCell>
            <TableCell className="text-right tabular-nums">v{run.rubric_version}</TableCell>
            <TableCell className="text-right tabular-nums">
              {run.report.labelled} of {run.report.episodes}
            </TableCell>
            <TableCell className="tabular-nums">{falseKeeps(run, "winnow")}</TableCell>
            <TableCell className="tabular-nums">{falseKeeps(run, "spark_alone")}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
