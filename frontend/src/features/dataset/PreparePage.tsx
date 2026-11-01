// Prepare: Dataset-level work that no Description depends on: ingest, hand-drawn boxes, wrist
// tracks, the Spark-alone baseline, and the exterior tracks and target boxes a box queues.
import { Progress } from "@/components/ui/progress";

import { Page, PageHeader } from "../core/PageHeader";
import { NeedsBox } from "../boxes/NeedsBox";
import { IngestForm } from "../episodes/IngestForm";
import { useEpisodes } from "../episodes/useEpisodes";
import { JobProgress } from "../jobs/JobProgress";
import { useIngestProgress } from "../jobs/useIngestProgress";
import { SetStatus } from "../sets/SetStatus";
import { TargetBoxes } from "../tracking/TargetBoxes";
import { useDatasetStatus, type DatasetStatus } from "./useDatasetStatus";

export function PreparePage() {
  const status = useDatasetStatus();
  const episodeList = useEpisodes();
  const job = useIngestProgress();

  const running = job.data ? !job.data.finished : false;
  return (
    <Page width="content">
      <PageHeader
        title={`${status.data?.name ?? "Dataset"} · Prepare`}
        subtitle={
          status.data &&
          `${String(status.data.episodes)} Episodes · Meta API spend so far $${status.data.cost_usd.toFixed(2)}`
        }
        info="Everything here belongs to the Dataset, not a Project: clips, tracks and hand-drawn boxes. Nothing here depends on a Description."
      />
      {status.data && <StatusGrid status={status.data} />}
      <SetStatus />
      <div className="mt-8 grid grid-cols-2 gap-4">
        <IngestForm disabled={running} />
        {job.data && <JobProgress job={job.data} />}
      </div>
      <NeedsBox episodes={episodeList.data ?? []} />
      <TargetBoxes episodes={episodeList.data ?? []} />
    </Page>
  );
}

function StatusGrid(props: { status: DatasetStatus }) {
  const { episodes, boxes, baseline } = props.status;
  const { wrist_tracks: wristTracks, wrist_no_closure: noClosure } = props.status;
  return (
    <>
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Episodes ingested" testId="episodes-ingested">
          {episodes}
        </Stat>
        <Stat label="Clips (H.264 + 5 fps)" of={episodes}>
          {episodes}
        </Stat>
        <Stat label="Hand-drawn boxes" of={episodes} testId="boxes-drawn">
          {boxes}
        </Stat>
        {baseline === null ? (
          <Stat label="Spark-alone baseline" muted note="needs MODEL_API_KEY">
            —
          </Stat>
        ) : (
          <Stat label="Spark-alone baseline" of={episodes} testId="baseline-done">
            {baseline}
          </Stat>
        )}
        {wristTracks === null ? (
          <Stat label="Wrist tracks" muted note="needs MODEL_API_KEY">
            —
          </Stat>
        ) : (
          <Stat
            label="Wrist tracks"
            of={episodes - noClosure}
            note={noClosure ? `${String(noClosure)} never closed the gripper` : undefined}
            testId="wrist-tracks"
          >
            {wristTracks}
          </Stat>
        )}
        <BoxStats status={props.status} />
      </div>
    </>
  );
}

// What a hand-drawn box queues: the exterior track, and the target box SAM finds or the
// curator draws.
function BoxStats(props: { status: DatasetStatus }) {
  const { boxes, exterior_tracks: exteriorTracks, target_boxes: targets } = props.status;
  const missing = props.status.targets_missing;
  return (
    <>
      {exteriorTracks === null ? (
        <Stat label="Exterior tracks" muted note="needs MODEL_API_KEY">
          —
        </Stat>
      ) : (
        <Stat label="Exterior tracks" of={boxes} testId="exterior-tracks">
          {exteriorTracks}
        </Stat>
      )}
      <Stat
        label="Target boxes"
        of={boxes}
        note={missing ? `${String(missing)} to draw by hand` : undefined}
        testId="target-boxes"
      >
        {targets}
      </Stat>
    </>
  );
}

function Stat(props: {
  label: string;
  children: number | string;
  of?: number;
  muted?: boolean;
  note?: string | undefined;
  testId?: string;
}) {
  const value = typeof props.children === "number" ? props.children : null;
  return (
    <div className="rounded-lg border p-3" data-testid={props.testId}>
      <div className="text-xs text-muted-foreground">{props.label}</div>
      <div className="mt-1 text-lg font-semibold tabular-nums">
        <span className={props.muted ? "text-muted-foreground" : undefined}>{props.children}</span>
        {props.of !== undefined && (
          <span className="text-sm font-normal text-muted-foreground"> of {props.of}</span>
        )}
      </div>
      {(props.muted === true || props.note !== undefined) && (
        <div className="text-[11px] text-muted-foreground">{props.note ?? "not built yet"}</div>
      )}
      {props.of !== undefined && value !== null && (
        <Progress value={props.of ? (value / props.of) * 100 : 0} className="mt-2 h-1" />
      )}
    </div>
  );
}
