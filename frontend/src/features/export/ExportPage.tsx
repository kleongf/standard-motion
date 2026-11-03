// Export: every Episode outside the Test set, by its Triage decision under the latest Rubric
// version, written as a LeRobot v3.0 dataset per source with the Reason for every Episode left
// out. Choose what to include, check the preview, export, then copy the folder; past exports
// are listed below.
import { useEffect, useState } from "react";

import { NextStep } from "../core/NextStep";
import { Page, PageHeader, SectionHeading } from "../core/PageHeader";
import { useLatestJob } from "../jobs/useLatestJob";
import { ExportButton } from "./ExportButton";
import { ExportStatus } from "./ExportStatus";
import { totalCounts, unlabelledWarning, writesText } from "./exportText";
import { IncludeChoice } from "./IncludeChoice";
import { PastExports } from "./PastExports";
import { PreviewTable } from "./PreviewTable";
import {
  useExportPreview,
  usePastExports,
  useRefreshPastExports,
  type ExportPreview,
  type Include,
} from "./useExport";

/** What the preview means for the export: what it writes, what it warns about, what it leaves
 * out, and why it would write nothing. */
function PreviewNotes(props: { preview: ExportPreview }) {
  const { preview } = props;
  const total = totalCounts(preview.sources);
  return (
    <div className="mt-3 grid gap-2 text-sm">
      {preview.nothing_exported === null ? (
        <p data-testid="export-writes">{writesText(preview)}</p>
      ) : (
        <p
          className="rounded-lg border border-dashed px-4 py-3 text-muted-foreground"
          data-testid="nothing-exported"
        >
          Nothing to export. {preview.nothing_exported}
        </p>
      )}
      {total.awaiting_label > 0 && (
        <p className="text-amber-800 dark:text-amber-300" data-testid="export-unlabelled">
          {unlabelledWarning(total.awaiting_label)}
        </p>
      )}
    </div>
  );
}

/** Refetch the past exports whenever the latest export finishes. */
function useLatestExport() {
  const job = useLatestJob("export").data;
  const refresh = useRefreshPastExports();
  const finished = job ? `${String(job.id)}:${String(job.finished)}` : "";
  useEffect(() => {
    void refresh();
  }, [finished, refresh]);
  return job;
}

export function ExportPage() {
  const [include, setInclude] = useState<Include>("keep");
  const preview = useExportPreview(include).data;
  const job = useLatestExport();
  const past = usePastExports().data ?? [];
  const running = job ? !job.finished : false;
  const empty = preview?.sources.length === 0;
  return (
    <Page width="content">
      <PageHeader
        title="Export"
        subtitle={preview && `Rubric v${String(preview.rubric_version)}`}
      />
      {empty ? (
        <NextStep page="prepare" action="Go to Prepare">
          No Episodes yet: ingest some on the Prepare page.
        </NextStep>
      ) : (
        <div className="grid gap-8">
          <section className="grid gap-3">
            <SectionHeading title="Include" />
            <IncludeChoice value={include} onChange={setInclude} />
          </section>
          <section>
            <SectionHeading title="Preview" />
            {preview && (
              <>
                <PreviewTable preview={preview} />
                <PreviewNotes preview={preview} />
              </>
            )}
            <div className="mt-4 grid max-w-2xl gap-3">
              <div>
                <ExportButton preview={preview} running={running} />
              </div>
              <ExportStatus job={job} latest={past[0]} />
            </div>
          </section>
          <section>
            <SectionHeading
              title="Past exports"
              meta={past.length > 0 ? String(past.length) : undefined}
            />
            <PastExports exports={past} />
          </section>
        </div>
      )}
    </Page>
  );
}
