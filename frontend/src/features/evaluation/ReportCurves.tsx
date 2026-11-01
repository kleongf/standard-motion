// Right reason and risk–coverage for Winnow and Spark alone: the headline k/n at the measured
// slack, then right reason over 0–3 s of slack, and risk against coverage from each system's
// confidence, so Winnow abstaining more can be weighed fairly.
import { SectionHeading } from "../core/PageHeader";
import { CurveChart, type Series } from "./CurveChart";
import { riskSeries, slackSeries } from "./curves";
import { countOf, interval, slackText } from "./reportText";
import type { EvaluationReport, RightReasonRow } from "./useEvaluation";

function AtSlack(props: { row: RightReasonRow }) {
  const p = props.row.at_slack;
  if (!p) return null;
  const range = interval(p);
  return (
    <span className="tabular-nums">
      {props.row.label} <span className="font-medium">{countOf(p)}</span>
      {range && <span className="text-muted-foreground"> ({range})</span>}
    </span>
  );
}

function RightReasonFigure(props: { report: EvaluationReport }) {
  const { slack, rows } = props.report.right_reason;
  const series: Series[] = rows.map((row) => ({
    system: row.system,
    label: row.label,
    points: slackSeries(row),
  }));
  // The curve's own extent (0–3 s); the measured slack is marked only when it falls inside.
  const maxSlack = Math.max(0, ...rows.flatMap((row) => row.curve.map((p) => p.slack_s)));
  const measured =
    slack.seconds !== null && slack.seconds <= maxSlack
      ? { x: slack.seconds, label: "measured" }
      : null;
  return (
    <div data-testid="right-reason">
      <SectionHeading
        level={3}
        title="Right reason on correct Rejects"
        info={
          <>
            A Reject is right when its Reason names a Phrase the Reference label fails, at a time
            inside that Phrase&apos;s labelled interval widened by the slack.
          </>
        }
      />
      <p className="mt-0.5 text-xs text-muted-foreground">{slackText(slack)}</p>
      {slack.seconds !== null && (
        <p className="mt-1.5 flex flex-wrap gap-x-4 text-sm" data-testid="right-reason-at-slack">
          {rows.map((row) => (
            <AtSlack key={row.system} row={row} />
          ))}
        </p>
      )}
      <div className="mt-2">
        <CurveChart
          title="Right reason over slack"
          series={series}
          xMax={maxSlack || 1}
          xLabel="Slack (s)"
          yLabel="Right, of correct Rejects"
          formatX={(s) => `${s.toFixed(2)} s`}
          marker={measured}
          empty="No correct Reject yet"
        />
      </div>
    </div>
  );
}

function RiskCoverageFigure(props: { report: EvaluationReport }) {
  const { risk_coverage: curves, matched_coverage: matched } = props.report;
  const series: Series[] = curves.map((curve) => ({
    system: curve.system,
    label: curve.label,
    points: riskSeries(curve),
  }));
  const operating =
    matched.episodes > 0 ? { x: matched.target / matched.episodes, label: "Winnow decides" } : null;
  return (
    <div data-testid="risk-coverage">
      <SectionHeading
        level={3}
        title="Risk–coverage"
        info={
          <>
            Each system&apos;s labelled Episodes, most confident first: the share it gets wrong
            among those it covers. Abstentions are ranked too, by the side they lean to. Spark
            alone&apos;s confidence is its samples&apos; agreement, (keeps + 1) / (answers + 2).
          </>
        }
      />
      <div className="mt-2">
        <CurveChart
          title="Risk against coverage"
          series={series}
          xMax={1}
          xLabel="Coverage"
          yLabel="Risk"
          formatX={(c) => `${(c * 100).toFixed(0)}%`}
          marker={operating}
          empty="No labelled Episode yet"
        />
      </div>
    </div>
  );
}

export function ReportCurves(props: { report: EvaluationReport }) {
  return (
    <div className="mt-8 grid gap-8 lg:grid-cols-2">
      <RightReasonFigure report={props.report} />
      <RiskCoverageFigure report={props.report} />
    </div>
  );
}
