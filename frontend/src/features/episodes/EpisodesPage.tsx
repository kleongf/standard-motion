// Every ingested Episode in a dense table, sorted into Triage tabs with its Reason (only once it
// has a Reference label; until then it's awaiting one and has no Triage decision), filterable by
// Phrase, Uncertainty signal and set, and sortable by confidence or quality; a row opens the
// full-page Workstation. The tab, filters, sort, open Episode and its start time live in the URL;
// J/K step through the Episodes shown. Export writes out the kept ones.
import { Page, PageHeader } from "../core/PageHeader";
import { navigate, useSearchParams } from "../core/url";
import { ExportButton } from "../export/ExportButton";
import { ExportStatus } from "../export/ExportStatus";
import { useRubric } from "../rubric/useRubric";
import { setsByEpisode, useSets } from "../sets/useSets";
import { countDecisions, parseTriageTab, TriageTabs, type TriageTab } from "../triage/TriageTabs";
import { useTriageList, type TriageList } from "../triage/useTriage";
import { EpisodeFilterBar } from "./EpisodeFilterBar";
import {
  applyFilters,
  nextSort,
  parseFilters,
  signalsIn,
  type EpisodeFilters,
} from "./episodeFilters";
import { EpisodePage } from "./EpisodePage";
import { EpisodeTable } from "./EpisodeTable";
import { useEpisodes, type Episode } from "./useEpisodes";

function open(id: string | null) {
  navigate({ episode: id, t: null });
}

/** How many were decided automatically and how many await a Reference label, under the
 * Rubric version; only the Episode count before anything is triaged. */
function summarize(episodes: Episode[], triage: TriageList | undefined): string {
  if (!triage) return `${String(episodes.length)} Episodes in the Dataset.`;
  const decided = countDecisions(triage.rows.map((r) => r.decision));
  const awaiting = episodes.filter((e) => !e.reference_labelled).length;
  return [
    ...(decided.all > 0
      ? [
          `${String(decided.all - decided.needs_review)} of ${String(decided.all)} decided automatically`,
          `${String(decided.needs_review)} Needs review`,
        ]
      : []),
    ...(awaiting > 0 ? [`${String(awaiting)} awaiting Reference label`] : []),
    `Rubric v${String(triage.rubric_version)}`,
  ].join(" · ");
}

function useTriagedEpisodes(tab: TriageTab, filters: EpisodeFilters) {
  const all = useEpisodes().data;
  const triage = useTriageList().data;
  const setOf = setsByEpisode(useSets().data);
  const triageOf = new Map(triage?.rows.map((r) => [r.episode_id, r]));
  const episodes = all ?? [];
  const filtered = applyFilters(episodes, filters, triageOf, setOf);
  const shown =
    tab === "all" ? filtered : filtered.filter((e) => triageOf.get(e.id)?.decision === tab);
  const counts = {
    ...countDecisions(filtered.flatMap((e) => triageOf.get(e.id)?.decision ?? [])),
    all: filtered.length,
  };
  const summary = summarize(episodes, triage);
  const signals = signalsIn(triage?.rows ?? []);
  return { loaded: all !== undefined, episodes, shown, triageOf, setOf, counts, summary, signals };
}

function OpenEpisode(props: { episode: Episode; ids: string[]; t: string | null }) {
  const t = Number(props.t ?? 0);
  return (
    <EpisodePage
      key={props.episode.id}
      episode={props.episode}
      ids={props.ids}
      initialT={Number.isFinite(t) ? t : 0}
      onOpen={open}
    />
  );
}

export function EpisodesPage() {
  const params = useSearchParams();
  const tab = parseTriageTab(params.get("triage"));
  const filters = parseFilters(params);
  const { loaded, episodes, shown, triageOf, setOf, counts, summary, signals } = useTriagedEpisodes(
    tab,
    filters,
  );
  const phrases = useRubric().data?.rubric.phrases ?? [];

  const openEpisode = episodes.find((e) => e.id === params.get("episode"));
  if (openEpisode) {
    const ids = shown.map((e) => e.id);
    const steps = ids.includes(openEpisode.id) ? ids : episodes.map((e) => e.id);
    return <OpenEpisode episode={openEpisode} ids={steps} t={params.get("t")} />;
  }

  return (
    <Page width="content">
      <PageHeader title="Episodes" subtitle={summary} actions={<ExportButton />} />
      <ExportStatus />
      {episodes.length === 0 && loaded && (
        <p className="text-sm text-muted-foreground">
          No Episodes yet: ingest some on the Prepare page.
        </p>
      )}
      {episodes.length > 0 && (
        <>
          <div>
            <TriageTabs
              tab={tab}
              counts={counts}
              onTab={(next) => {
                navigate({ triage: next === "all" ? null : next });
              }}
            />
          </div>
          <EpisodeFilterBar filters={filters} phrases={phrases} signals={signals} />
          <EpisodeTable
            episodes={shown}
            triageOf={triageOf}
            setOf={setOf}
            sort={filters.sort}
            onSort={(column) => {
              navigate({ sort: nextSort(filters.sort, column) });
            }}
            onOpen={open}
          />
          {shown.length === 0 && (
            <p className="mt-4 text-sm text-muted-foreground">
              No Episodes match this tab and these filters.
            </p>
          )}
        </>
      )}
    </Page>
  );
}
