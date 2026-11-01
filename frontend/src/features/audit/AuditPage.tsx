// Audit: a seeded sample of Winnow's own Keeps (and a few Rejects), drawn once per Rubric version
// and margin multiplier s (calibrating the version changes its Keeps, so it is drawn afresh)
// from the Episodes outside the Test set. The auditor marks each Good or Bad; the header states
// Keep precision. The first unmarked item opens; `?episode=` picks another from the strip.
import { Button } from "@/components/ui/button";

import { sText } from "../calibration/calibrationText";
import { Page, PageHeader } from "../core/PageHeader";
import { navigate, useSearchParams } from "../core/url";
import { useEpisodes, type Episode } from "../episodes/useEpisodes";
import { Workstation } from "../episodes/Workstation";
import { AuditCall } from "./AuditCall";
import { precisionText } from "./precisionText";
import { SampleStrip } from "./SampleStrip";
import { useAudit, useDrawSample, useMarkItem, type AuditItem, type AuditSample } from "./useAudit";

export function AuditPage() {
  const params = useSearchParams();
  const audit = useAudit();
  const episodes = new Map((useEpisodes().data ?? []).map((e) => [e.id, e]));
  const sample = audit.data;
  const items = sample?.items ?? [];
  const current =
    items.find((i) => i.episode_id === params.get("episode")) ??
    items.find((i) => i.mark === null) ??
    items[0];
  const episode = current && episodes.get(current.episode_id);

  return (
    <Page width="full">
      <AuditHeader sample={sample} current={current} />
      {sample && current ? (
        <>
          {episode && (
            // Keyed so each Episode starts with its own playhead and save state.
            <AuditWorkstation
              key={episode.id}
              item={current}
              phrases={sample.phrases}
              episode={episode}
            />
          )}
          <SampleStrip
            items={items}
            current={current}
            episodes={episodes}
            onOpen={(id) => {
              navigate({ episode: id, t: null });
            }}
          />
        </>
      ) : (
        <SampleStatus audit={audit} />
      )}
    </Page>
  );
}

/** What shows without a sample: loading, an error, or the button that draws one. */
function SampleStatus(props: { audit: ReturnType<typeof useAudit> }) {
  const { audit } = props;
  const drawSample = useDrawSample();
  if (audit.isPending) return <p className="text-sm text-muted-foreground">Loading the sample…</p>;
  if (audit.isError) return <p className="text-sm text-destructive">{audit.error.message}</p>;
  return (
    <div className="max-w-xl rounded-md border p-4">
      <p className="text-sm">
        Check a random sample of the Episodes Winnow decided on its own: up to 12 Keeps and 5
        Rejects with a Reference label, none from the Test set. It’s drawn once for Rubric v
        {audit.data.rubric_version} at s = {sText(audit.data.s)}, with its seed recorded.
      </p>
      {audit.data.earlier_s !== null && (
        <p className="mt-2 text-sm text-amber-800 dark:text-amber-300" data-testid="audit-redraw">
          Calibration changed s from {sText(audit.data.earlier_s)} to {sText(audit.data.s)} since
          the last sample, and with it which Episodes Winnow keeps: draw a fresh sample. Episodes
          drawn again keep their marks.
        </p>
      )}
      <Button
        size="sm"
        className="mt-3"
        disabled={drawSample.isPending}
        onClick={() => {
          drawSample.mutate();
        }}
      >
        Draw the sample
      </Button>
      {drawSample.isError && (
        <p role="alert" className="mt-2 text-xs text-destructive">
          {drawSample.error.message}
        </p>
      )}
    </div>
  );
}

function AuditHeader(props: { sample: AuditSample | undefined; current: AuditItem | undefined }) {
  const { sample, current } = props;
  const items = sample?.items ?? [];
  const marked = items.filter((i) => i.mark !== null).length;
  return (
    <PageHeader
      title="Audit"
      subtitle={
        sample?.seed == null
          ? "Keep precision, from a seeded sample"
          : `${String(marked)} of ${String(items.length)} marked · Rubric v${String(sample.rubric_version)} · seed ${String(sample.seed)} · drawn at s = ${sText(sample.s)}`
      }
      progress={sample?.seed == null ? undefined : marked / Math.max(1, items.length)}
      actions={
        sample?.seed != null && (
          <div className="text-right text-sm">
            <div className="text-xs text-muted-foreground">Keep precision</div>
            <div className="font-medium tabular-nums" data-testid="audit-precision">
              {precisionText(sample.precision)}
            </div>
            {current && (
              <div className="text-xs text-muted-foreground" data-testid="audit-current">
                {current.episode_id}
              </div>
            )}
          </div>
        )
      }
    />
  );
}

/** The Workstation with the audit call in its actions slot; each mark is `audit` labels. */
function AuditWorkstation(props: { item: AuditItem; phrases: string[]; episode: Episode }) {
  const { item, phrases, episode } = props;
  const mark = useMarkItem();
  return (
    <Workstation
      episode={episode}
      actions={
        <>
          <AuditCall
            item={item}
            phrases={phrases}
            pending={mark.isPending}
            onGood={() => {
              mark.mutate({ episodeId: item.episode_id, value: "pass", phrases });
            }}
            onBad={(phrase) => {
              mark.mutate({ episodeId: item.episode_id, value: "fail", phrases: [phrase] });
            }}
          />
          {mark.isError && <p className="-mt-2 text-xs text-destructive">{mark.error.message}</p>}
        </>
      }
    />
  );
}
