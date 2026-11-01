// Keep precision at matched coverage, McNemar's discordant counts, and failures per Phrase:
// counts first, intervals after, never "±".
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { SectionHeading } from "../core/PageHeader";
import { countOf, interval } from "./reportText";
import type { EvaluationReport, MatchedCoverage, McNemar, PhraseFailures } from "./useEvaluation";

function Matched(props: { matched: MatchedCoverage }) {
  const { matched } = props;
  return (
    <div data-testid="matched-coverage">
      <SectionHeading
        level={3}
        title="Keep precision at matched coverage"
        meta={`Winnow decides ${String(matched.target)} of ${String(matched.episodes)}`}
        info={
          <>
            Winnow decides {matched.target} of {matched.episodes} Episodes; Spark alone is held to
            its most confident Episodes up to that many, never splitting a tie.
          </>
        }
      />
      <Table className="mt-2" aria-label="Matched coverage">
        <TableHeader>
          <TableRow>
            <TableHead>System</TableHead>
            <TableHead className="text-right">Covered</TableHead>
            <TableHead>Keeps meeting the Description</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {matched.rows.map((row) => {
            const range = interval(row.keep_precision);
            return (
              <TableRow key={row.system}>
                <TableCell className="font-medium">{row.label}</TableCell>
                <TableCell className="text-right tabular-nums">{row.covered}</TableCell>
                <TableCell className="tabular-nums">
                  {countOf(row.keep_precision)}
                  {range && <span className="ml-2 text-xs text-muted-foreground">{range}</span>}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function Discordant(props: { mcnemar: McNemar }) {
  const m = props.mcnemar;
  return (
    <div data-testid="mcnemar">
      <SectionHeading
        level={3}
        title="McNemar discordant pairs"
        meta={`${String(m.compared)} both decided`}
        info={
          <>
            On the {m.compared} Episodes both decided, those only one of them got right. Counts
            only.
          </>
        }
      />
      <dl className="mt-2 flex gap-8 text-sm">
        <div>
          <dt className="text-xs text-muted-foreground">Only Winnow right</dt>
          <dd className="text-2xl font-medium">{m.winnow_only_right}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Only Spark alone right</dt>
          <dd className="text-2xl font-medium">{m.spark_alone_only_right}</dd>
        </div>
      </dl>
    </div>
  );
}

function PhraseTable(props: { phrases: PhraseFailures[] }) {
  return (
    <div data-testid="phrase-failures">
      <SectionHeading
        level={3}
        title="Failures per Phrase"
        info={
          <>
            Labelled failures of each Phrase and how many each system rejected. Under 5 failures is
            too few to score.
          </>
        }
      />
      <Table className="mt-2" aria-label="Failures per Phrase">
        <TableHeader>
          <TableRow>
            <TableHead>Phrase</TableHead>
            <TableHead className="text-right">Failures</TableHead>
            <TableHead className="text-right">Winnow rejects</TableHead>
            <TableHead className="text-right">Spark alone rejects</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {props.phrases.map((p) => (
            <TableRow key={p.phrase} className={p.too_few ? "text-muted-foreground" : undefined}>
              <TableCell className="whitespace-normal">“{p.phrase}”</TableCell>
              <TableCell className="text-right tabular-nums">{p.failures}</TableCell>
              <TableCell className="text-right tabular-nums">{p.winnow_rejects}</TableCell>
              <TableCell className="text-right tabular-nums">{p.spark_alone_rejects}</TableCell>
              <TableCell className="text-xs">{p.too_few ? "Too few to score" : ""}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export function ReportBreakdown(props: { report: EvaluationReport }) {
  return (
    <>
      <div className="mt-8 grid gap-8 lg:grid-cols-2">
        <Matched matched={props.report.matched_coverage} />
        <Discordant mcnemar={props.report.mcnemar} />
      </div>
      <div className="mt-8">
        <PhraseTable phrases={props.report.phrase_failures} />
      </div>
    </>
  );
}
