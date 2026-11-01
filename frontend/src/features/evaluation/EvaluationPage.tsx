// The Evaluation page: Winnow against Spark alone and length alone, scored on the Episodes with
// a Reference label, for a set and a Rubric version, with the source ablation, tracking health,
// cost and the Dataset outcome; `winnow eval` returns the same report. Below it, the live list of
// Episodes where Spark alone and Winnow disagree.
import { useState } from "react";

import { Button } from "@/components/ui/button";

import { Page, PageHeader, SectionHeading } from "../core/PageHeader";
import { Tabs } from "../core/Tabs";
import { useRubric } from "../rubric/useRubric";
import { SET_LABELS, type SetName } from "../sets/useSets";
import { AblationTable, TrackingHealthTable } from "./AblationTable";
import { ComparisonTable } from "./ComparisonTable";
import { CostSummary } from "./CostSummary";
import { DatasetOutcomeSection } from "./DatasetOutcomeSection";
import { DisagreementList } from "./DisagreementList";
import { ReportBreakdown } from "./ReportBreakdown";
import { ReportCurves } from "./ReportCurves";
import { TestRunLog } from "./TestRunLog";
import { useRunEvaluation, type EvaluationReport } from "./useEvaluation";

const SETS: SetName[] = ["dev", "test"];

function summary(report: EvaluationReport): string {
  const failures = report.description_failures;
  return [
    SET_LABELS[report.set_name],
    `Rubric v${String(report.rubric_version)}`,
    `${String(report.labelled)} of ${String(report.episodes)} Episodes labelled`,
    `${String(failures)} description ${failures === 1 ? "failure" : "failures"}`,
  ].join(" · ");
}

/** Any Rubric version, newest first; null runs the latest. */
function RubricVersionSelect(props: {
  value: number | null;
  onChange: (version: number | null) => void;
}) {
  const latest = useRubric().data?.version ?? 0;
  const versions = Array.from({ length: latest }, (_, i) => latest - i);
  return (
    <label className="ml-2 flex items-center gap-2 text-sm">
      Rubric
      <select
        className="h-7 rounded-md border bg-background px-2 text-sm dark:bg-input/30"
        value={props.value ?? ""}
        onChange={(e) => {
          props.onChange(e.target.value === "" ? null : Number(e.target.value));
        }}
      >
        <option value="">{latest > 0 ? `latest (v${String(latest)})` : "latest"}</option>
        {versions.map((v) => (
          <option key={v} value={v}>
            v{v}
          </option>
        ))}
      </select>
    </label>
  );
}

export function EvaluationPage() {
  const [setName, setSetName] = useState<SetName>("dev");
  const [version, setVersion] = useState<number | null>(null); // null: the latest
  const [shown, setShown] = useState<{ report: EvaluationReport; runId: number | null }>();
  const run = useRunEvaluation();

  const start = () => {
    run.mutate(
      { set_name: setName, rubric_version: version },
      {
        onSuccess: (report) => {
          setShown({ report, runId: null });
        },
      },
    );
  };

  return (
    <Page width="content">
      <PageHeader
        title="Evaluation"
        info="Winnow against Spark alone and length alone, scored on the Episodes with a Reference label. Interview and review labels count on the Dev set only, never on the Test set."
      >
        <Tabs
          label="Set"
          items={SETS.map((s) => ({
            value: s,
            label: SET_LABELS[s],
            disabled: run.isPending, // a run's report shows under its own set
          }))}
          value={setName}
          onChange={(s) => {
            setSetName(s);
            setShown(undefined);
          }}
        />
        <RubricVersionSelect value={version} onChange={setVersion} />
        <Button size="sm" className="ml-auto" disabled={run.isPending} onClick={start}>
          {run.isPending ? "Scoring…" : `Run on the ${SET_LABELS[setName]}`}
        </Button>
      </PageHeader>
      {run.error && <p className="mt-3 text-sm text-destructive">{run.error.message}</p>}
      {shown ? (
        <section className="mt-6">
          <h2 className="text-sm font-medium" data-testid="report-summary">
            {summary(shown.report)}
          </h2>
          <ComparisonTable report={shown.report} />
          <ReportCurves report={shown.report} />
          <ReportBreakdown report={shown.report} />
          <div className="mt-8 grid gap-8 lg:grid-cols-[3fr_2fr]">
            <AblationTable rows={shown.report.ablation} />
            <TrackingHealthTable rows={shown.report.tracking_health} />
          </div>
          <div className="mt-8">
            <CostSummary cost={shown.report.cost} time={shown.report.review_time} />
          </div>
          <DatasetOutcomeSection
            outcome={shown.report.dataset_outcome}
            failbench={shown.report.failbench}
          />
        </section>
      ) : (
        <p className="mt-6 text-sm text-muted-foreground">
          Run a set, or open a logged Test set run below, to see the comparison.
        </p>
      )}
      <section className="mt-10">
        <DisagreementList />
      </section>
      <section className="mt-10">
        <SectionHeading
          title="Test run log"
          info="Every Test set run is logged with its date and Rubric version; the numbers reported are the last run before the freeze."
        />
        <TestRunLog
          shownId={shown?.runId ?? null}
          onShow={(r) => {
            setSetName("test");
            setShown({ report: r.report, runId: r.id });
          }}
        />
      </section>
    </Page>
  );
}
