// The Workstation's link between its Criterion results and its video: which result is open,
// and focusing one (from a lane, a moment chip or Evidence) opens it on its camera and seeks.
// While blind (Reference label mode) there is no triage to show, nor while the Episode is
// `awaiting` its Reference label: the server withholds it until then.
import { useState } from "react";

import { laneFocus } from "./laneFocus";
import { useEpisodeTriage, type CriterionResult } from "./useTriage";

export function useTriageFocus(
  episode: { id: string; cameras: string[]; reference_labelled: boolean },
  blind: boolean,
  seek: (t: number) => void,
  setCamera: (camera: string) => void,
) {
  const awaiting = !blind && !episode.reference_labelled;
  const hidden = blind || awaiting;
  const fetched = useEpisodeTriage(episode.id, !hidden).data;
  const triage = hidden ? undefined : fetched; // cached data outlives `enabled: false`
  const [openId, setOpenId] = useState<string | null>(null);

  /** Open a result, show its camera, and seek to `t` or to the result's own moment. */
  const focus = (result: CriterionResult, t?: number) => {
    const target = laneFocus(result, episode.cameras);
    setOpenId(result.criterion_id);
    if (target.camera) setCamera(target.camera);
    seek(t ?? target.t);
  };

  return { triage, awaiting, openId, setOpenId, focus };
}
