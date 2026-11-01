// What a run costs: Meta spend per 1,000 Episodes, extrapolated from the set's cost log (not run
// at 1,000), beside the human cost per Episode left, and the review minutes Winnow saves.
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { SectionHeading } from "../core/PageHeader";
import { countOf, minutesText, usdText } from "./reportText";
import type { MetaCost, ReviewTime } from "./useEvaluation";

function Stat(props: { label: string; value: string; note: string; testId: string }) {
  return (
    <div data-testid={props.testId}>
      <dt className="text-xs text-muted-foreground">{props.label}</dt>
      <dd className="text-2xl font-medium tabular-nums">{props.value}</dd>
      <dd className="text-xs text-muted-foreground">{props.note}</dd>
    </div>
  );
}

function StepTable(props: { cost: MetaCost }) {
  return (
    <Table className="mt-3" aria-label="Cost by step">
      <TableHeader>
        <TableRow>
          <TableHead>Step</TableHead>
          <TableHead className="text-right">Paid calls</TableHead>
          <TableHead className="text-right">Episodes</TableHead>
          <TableHead className="text-right">Spent</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {props.cost.steps.map((s) => (
          <TableRow key={s.step}>
            <TableCell>
              {s.label}
              {s.system !== "winnow" && (
                <span className="ml-2 text-xs text-muted-foreground">evaluation only</span>
              )}
            </TableCell>
            <TableCell className="text-right tabular-nums">{s.calls}</TableCell>
            <TableCell className="text-right tabular-nums">{s.episodes}</TableCell>
            <TableCell className="text-right tabular-nums">{usdText(s.usd)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function CostSummary(props: { cost: MetaCost; time: ReviewTime }) {
  const { cost, time } = props;
  const reviewed = `${countOf(time.needs_review)} Episodes at ${minutesText(time.minutes_per_episode)}`;
  return (
    <div data-testid="cost">
      <SectionHeading
        level={3}
        title="Cost per 1,000 Episodes"
        meta={`from ${String(cost.episodes)} Episodes`}
        info={
          <>
            Extrapolated from every paid call on this set&apos;s {cost.episodes} Episodes in the
            Meta cost log, re-runs included (×10 for a Test set of 100); cache hits are free. Rubric
            compiles so far cost {usdText(cost.compile_usd)}, once per Project.
          </>
        }
      />
      <dl className="mt-3 grid grid-cols-2 gap-6 md:grid-cols-4">
        <Stat
          testId="cost-winnow"
          label="Winnow, Meta calls"
          value={usdText(cost.winnow_per_1000_usd)}
          note={`${usdText(cost.winnow_usd)} on this set`}
        />
        <Stat
          testId="cost-spark-alone"
          label="Spark alone, Meta calls"
          value={usdText(cost.spark_alone_per_1000_usd)}
          note={`${usdText(cost.spark_alone_usd)} on this set, with the FailBench check`}
        />
        <Stat
          testId="human-cost"
          label="Human cost per Episode"
          value={minutesText(time.needs_review_minutes_per_episode)}
          note={`Needs review (${reviewed}), plus one hand-drawn box, timed within labelling`}
        />
        <Stat
          testId="minutes-saved"
          label="Review minutes saved"
          value={minutesText(time.minutes_saved)}
          note={`${minutesText(time.minutes_per_episode)} per Episode on the label-mode timer × ${String(time.decided)} decided automatically`}
        />
      </dl>
      {cost.steps.length > 0 && <StepTable cost={cost} />}
    </div>
  );
}
