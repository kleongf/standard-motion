// The counts behind the sidebar's step notes and its next step, read from the queries the pages
// themselves use (so they stay cached and in step). A query that fails, such as the Audit sample
// before any Run, leaves its count unknown.
import { useAudit } from "../audit/useAudit";
import { useEpisodes } from "../episodes/useEpisodes";
import { useReviewQueue } from "../review/useReview";
import { useVersions } from "../rubric/useRubric";
import { useTriageList } from "../triage/useTriage";
import type { FlowCounts } from "./flow";

function latest(versions: { version: number }[] | undefined) {
  if (!versions) return undefined;
  return versions.length > 0 ? Math.max(...versions.map((v) => v.version)) : null;
}

export function useFlow(): FlowCounts {
  const episodes = useEpisodes().data;
  const version = latest(useVersions().data);
  const triage = useTriageList().data;
  const review = useReviewQueue().data;
  const audit = useAudit().data;
  return {
    episodes: episodes?.length,
    labelled: episodes?.filter((e) => e.reference_labelled).length,
    version,
    shown: triage?.rows.length,
    waiting: review?.items.length,
    auditLeft: audit && (audit.drawn_at ? audit.items.filter((i) => i.mark === null).length : null),
  };
}
