// The Workstation (#8, Variant A): the instruction and camera tabs over one large video, one
// playhead driving the video, a lane per Criterion and the robot-data plots, and a right panel
// with the Triage decision, Reason, Criterion results and a closed Details. Review and Reference label mode put their controls in
// `actions`. `blind` (Reference label mode) hides every Winnow and baseline output: tracks,
// lanes, the Triage decision, Reason and Criterion results. An Episode without a Reference label
// has no lanes or Triage decision to show either: the server withholds them until it's labelled.
import { useEffect, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";

import { Tabs } from "../core/Tabs";
import { AwaitingLabelNote } from "../referenceLabels/AwaitingLabel";
import { useSignalLevels } from "../rubric/useRubric";
import { TargetOverlay } from "../tracking/TargetOverlay";
import { TrackOverlay } from "../tracking/TrackOverlay";
import { useTracks, type Track } from "../tracking/useTracks";
import { CriterionLanes } from "../triage/CriterionLanes";
import { TrackPlots } from "../triage/TrackPlots";
import { TriagePanel } from "../triage/TriagePanel";
import { useTriageFocus } from "../triage/useTriageFocus";
import { EpisodeDetails } from "./EpisodeDetails";
import { EpisodeVideo } from "./EpisodeVideo";
import { SignalPlots } from "./SignalPlots";
import { clipUrl, useSignals, type Episode } from "./useEpisodes";
import { usePlayhead, type Playhead } from "./usePlayhead";

const CAMERA_LABELS: Record<string, string> = {
  exterior_image_1_left: "Exterior 1",
  exterior_image_2_left: "Exterior 2",
  wrist_image_left: "Wrist",
};

export function Workstation(props: {
  episode: Episode;
  initialT?: number;
  actions?: Actions;
  blind?: boolean;
}) {
  const { episode } = props;
  const playhead = usePlayhead(episode.duration_s, props.initialT);
  const [camera, setCamera] = useState(episode.cameras[0] ?? null);
  const signals = useSignals(episode.id);
  const blind = props.blind ?? false;
  const tracks = useShownTracks(episode.id, blind);
  const shownTrack = tracks.find((t) => t.camera === camera && t.status === "tracked");
  const levels = useSignalLevels(!blind);
  const { toggle, seek } = playhead;
  const { triage, awaiting, openId, setOpenId, focus } = useTriageFocus(
    episode,
    blind,
    seek,
    setCamera,
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const typing =
        event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement;
      if (event.key !== " " || typing) return;
      event.preventDefault();
      toggle();
    };
    globalThis.addEventListener("keydown", onKey);
    return () => {
      globalThis.removeEventListener("keydown", onKey);
    };
  }, [toggle]);

  return (
    <div className="grid grid-cols-[minmax(0,1fr)_340px] gap-4">
      <section className="min-w-0">
        <CameraBar episode={episode} camera={camera} onCamera={setCamera} />
        <VideoView
          episodeId={episode.id}
          camera={camera}
          playhead={playhead}
          track={shownTrack}
          blind={blind}
        />
        <Transport playhead={playhead} duration={episode.duration_s} canPlay={camera !== null} />
        {triage && (
          <CriterionLanes
            results={triage.criteria}
            duration={episode.duration_s}
            t={playhead.t}
            openId={openId}
            onFocus={focus}
          />
        )}
        {signals.data && (
          <SignalPlots
            signals={signals.data}
            playhead={playhead}
            duration={episode.duration_s}
            levels={levels}
          />
        )}
        {triage && (
          <TrackPlots
            results={triage.criteria}
            playhead={playhead}
            duration={episode.duration_s}
            onFocus={focus}
          />
        )}
      </section>
      <aside className="flex min-w-0 flex-col gap-4 self-start rounded-xl border bg-card p-4">
        {renderActions(props.actions, playhead)}
        {awaiting && <AwaitingLabelNote />}
        {triage && (
          <TriagePanel
            triage={triage}
            openId={openId}
            onOpen={setOpenId}
            onFocus={focus}
            onSeek={seek}
          />
        )}
        <EpisodeDetails
          episode={episode}
          tracks={tracks}
          blind={blind}
          rubricVersion={triage?.rubric_version}
        />
      </aside>
    </div>
  );
}

/** The instruction, the one fact a reviewer reads first, beside the camera tabs. */
function CameraBar(props: {
  episode: Episode;
  camera: string | null;
  onCamera: (camera: string) => void;
}) {
  const { episode } = props;
  const { instruction } = episode;
  return (
    <div className="mb-2 flex items-center gap-3">
      <p
        className="min-w-0 flex-1 truncate text-lg leading-snug font-semibold tracking-tight"
        title={instruction ?? undefined}
      >
        {instruction ? (
          <>“{instruction}”</>
        ) : (
          <span className="font-normal text-muted-foreground">No instruction recorded</span>
        )}
      </p>
      <Tabs
        label="Camera"
        items={episode.cameras.map((c) => ({ value: c, label: CAMERA_LABELS[c] ?? c }))}
        value={props.camera ?? ""}
        onChange={props.onCamera}
      />
    </div>
  );
}

function VideoView(props: {
  episodeId: string;
  camera: string | null;
  playhead: Playhead;
  track: Track | undefined;
  blind: boolean;
}) {
  const { camera, playhead } = props;
  if (!camera) {
    return (
      <div className="grid aspect-video w-full place-items-center rounded bg-black text-sm text-white/60">
        No clips for this Episode
      </div>
    );
  }
  return (
    <div className="relative">
      <EpisodeVideo key={camera} src={clipUrl(props.episodeId, camera)} playhead={playhead} />
      {props.track && <TrackOverlay track={props.track} playhead={playhead} />}
      <TargetOverlay episodeId={props.episodeId} camera={camera} hidden={props.blind} />
    </div>
  );
}

type Actions = ReactNode | ((playhead: Playhead) => ReactNode);

function renderActions(actions: Actions, playhead: Playhead): ReactNode {
  return typeof actions === "function" ? actions(playhead) : actions;
}

/** None while blind: tracks are what tracked Criteria read. */
function useShownTracks(episodeId: string, blind: boolean): Track[] {
  const fetched = useTracks(episodeId, !blind).data; // cached data outlives `enabled: false`
  return blind ? [] : (fetched ?? []);
}

function Transport(props: { playhead: Playhead; duration: number; canPlay: boolean }) {
  const { playhead } = props;
  return (
    <div className="my-2 flex items-center gap-2.5">
      <Button size="sm" variant="outline" disabled={!props.canPlay} onClick={playhead.toggle}>
        {playhead.playing ? "Pause" : "Play"}
      </Button>
      <input
        type="range"
        aria-label="Playhead"
        min={0}
        max={props.duration}
        step={1 / 15}
        value={playhead.t}
        onChange={(event) => {
          playhead.seek(Number(event.target.value));
        }}
        className="flex-1 accent-primary"
      />
      <span className="w-24 text-right text-xs text-muted-foreground tabular-nums">
        <span className="text-sm font-semibold text-foreground">{playhead.t.toFixed(1)}</span> /{" "}
        {props.duration.toFixed(1)} s
      </span>
    </div>
  );
}
