// Winnow and the baselines side by side: counts first, each rate's 95% Wilson interval under it.
// This is the only place Spark alone appears in the app.
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { InfoTip } from "../core/InfoTip";
import { Rate } from "./Rate";
import { balancedAccuracyText, lengthRuleText } from "./reportText";
import type { EvaluationReport } from "./useEvaluation";

export function ComparisonTable(props: { report: EvaluationReport }) {
  const { comparison } = props.report;
  return (
    <>
      <Table className="mt-3" aria-label="Comparison">
        <TableHeader>
          <TableRow>
            <TableHead>System</TableHead>
            <TableHead className="text-right">Keeps</TableHead>
            <TableHead className="text-right">Rejects</TableHead>
            <TableHead className="text-right">Undecided</TableHead>
            <TableHead>False keeps</TableHead>
            <TableHead>False rejects</TableHead>
            <TableHead>Coverage</TableHead>
            <TableHead className="text-right">Balanced accuracy</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {comparison.rows.map((row) => (
            <TableRow key={row.system} data-testid={`system-${row.system}`}>
              <TableCell className="font-medium">{row.label}</TableCell>
              <TableCell className="text-right tabular-nums">{row.keeps}</TableCell>
              <TableCell className="text-right tabular-nums">{row.rejects}</TableCell>
              <TableCell className="text-right tabular-nums">{row.undecided}</TableCell>
              <TableCell>
                <Rate p={row.false_keeps} />
              </TableCell>
              <TableCell>
                <Rate p={row.false_rejects} />
              </TableCell>
              <TableCell>
                <Rate p={row.coverage} />
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {balancedAccuracyText(row.balanced_accuracy)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="mt-3 flex items-center gap-1 text-xs text-muted-foreground">
        {lengthRuleText(comparison.length_rule)}
        <InfoTip label="these columns">
          False keeps count description failures kept, of all description failures; false rejects
          count Episodes meeting the Description that were rejected; coverage counts Episodes
          decided without a person; balanced accuracy averages failures rejected and Episodes
          meeting the Description kept, over the Episodes each system decided. Ranges are 95% Wilson
          intervals. Undecided is Winnow&apos;s Needs review, or Spark alone with no majority
          answer.
        </InfoTip>
      </p>
    </>
  );
}
