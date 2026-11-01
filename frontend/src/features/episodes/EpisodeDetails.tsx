// The foot of the Workstation panel: warnings worth seeing at once, then the Episode's own facts
// (source, frames, Rubric version, set, track and target health) behind a closed Details.
import { ChevronRight } from "lucide-react";

import { SET_LABELS, setsByEpisode, useSets } from "../sets/useSets";
import { TargetStatus } from "../tracking/TargetStatus";
import { TrackStatus } from "../tracking/TrackStatus";
import { TrackWarnings } from "../tracking/TrackWarnings";
import type { Track } from "../tracking/useTracks";
import { Pill } from "../triage/Pill";
import { PANEL_LABEL } from "../triage/TriagePanel";
import type { Episode } from "./useEpisodes";

export function EpisodeDetails(props: {
  episode: Episode;
  tracks: Track[];
  blind: boolean;
  rubricVersion?: number | undefined;
}) {
  const { episode } = props;
  const set = setsByEpisode(useSets().data).get(episode.id);
  return (
    <div className="border-t pt-2.5">
      <TrackWarnings episodeId={episode.id} tracks={props.tracks} hidden={props.blind} />
      <details className="group">
        <summary
          className={`${PANEL_LABEL} flex cursor-pointer list-none items-center gap-1 hover:text-foreground [&::-webkit-details-marker]:hidden`}
        >
          <ChevronRight className="size-3 transition-transform group-open:rotate-90" />
          Details
        </summary>
        <dl className="mt-2 grid grid-cols-[6rem_minmax(0,1fr)] items-baseline gap-y-1 text-xs">
          <dt className="text-muted-foreground">Episode</dt>
          <dd className="tabular-nums">
            {episode.source} · {episode.index}
          </dd>
          <dt className="text-muted-foreground">Frames</dt>
          <dd className="tabular-nums">
            {episode.frames} at {episode.fps} Hz · {episode.duration_s.toFixed(1)} s
          </dd>
          {props.rubricVersion !== undefined && (
            <>
              <dt className="text-muted-foreground">Rubric</dt>
              <dd className="tabular-nums">v{props.rubricVersion}</dd>
            </>
          )}
          <dt className="text-muted-foreground">Set</dt>
          <dd>
            <Pill tone="neutral">
              <span data-testid="episode-set">{set ? SET_LABELS[set] : "None"}</span>
            </Pill>
          </dd>
          {props.tracks.map((track) => (
            <TrackStatus key={track.kind} track={track} />
          ))}
          <TargetStatus episodeId={episode.id} hidden={props.blind} />
        </dl>
      </details>
    </div>
  );
}
