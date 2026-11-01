// Reference label mode: blind labels for every Episode of the Test set and Dev set against the
// frozen Description, then a relabel pass over about 15 Dev set Episodes. The queue lives in
// `?queue=`, the open Episode in `?episode=`.
import { Button } from "@/components/ui/button";

import { Page, PageHeader } from "../core/PageHeader";
import { Tabs } from "../core/Tabs";
import { navigate, useSearchParams } from "../core/url";
import { useEpisodes } from "../episodes/useEpisodes";
import { useSets } from "../sets/useSets";
import { LabelSession } from "./LabelSession";
import { labelQueue, QUEUE_LABELS, queueMembers, type LabelQueue } from "./queue";
import { QueueTable } from "./QueueTable";
import { useFrozenDescription, useReferenceLabels } from "./useReferenceLabels";

const QUEUES = Object.keys(QUEUE_LABELS) as LabelQueue[];

function readQueue(value: string | null): LabelQueue {
  return QUEUES.find((q) => q === value) ?? "test";
}

export function ReferenceLabelsPage() {
  const params = useSearchParams();
  const queue = readQueue(params.get("queue"));
  const episodes = useEpisodes().data ?? [];
  const sets = useSets().data;
  const labels = useReferenceLabels().data;
  const description = useFrozenDescription().data;
  const remaining = labelQueue(queue, sets, labels);
  const open = (id: string | null) => {
    navigate({ episode: id, t: null });
  };

  const openEpisode = episodes.find((e) => e.id === params.get("episode"));
  if (openEpisode && description) {
    return (
      <LabelSession
        key={openEpisode.id}
        episode={openEpisode}
        queue={queue}
        remaining={remaining}
        phrases={description.phrases}
        onOpen={open}
      />
    );
  }

  const members = queueMembers(queue, sets);
  const byId = new Map(episodes.map((e) => [e.id, e]));
  return (
    <Page width="content">
      <PageHeader
        title="Reference labels"
        subtitle={description && `“${description.text}”`}
        info="Label blind, before any tuning: no Triage decision, Criterion result or baseline answer shows here, and an Episode's Dataset outcome appears only once it's labelled."
      />
      <div className="flex items-center gap-2">
        <Tabs
          label="Queue"
          items={QUEUES.map((q) => ({
            value: q,
            label: QUEUE_LABELS[q],
            count: labelQueue(q, sets, labels).length,
          }))}
          value={queue}
          onChange={(q) => {
            navigate({ queue: q, episode: null });
          }}
        />
        <Button
          size="sm"
          className="ml-auto"
          disabled={remaining.length === 0}
          onClick={() => {
            open(remaining[0] ?? null);
          }}
        >
          {queue === "relabel" ? "Start relabelling" : "Start labelling"} ({remaining.length})
        </Button>
      </div>
      {queue === "relabel" && (
        <p className="mt-2 text-xs text-muted-foreground">
          A day after the first pass, relabel about 15 Dev set Episodes. They are kept apart from
          the first pass and measure how far your own interval edges move.
        </p>
      )}
      <QueueTable
        episodes={members.flatMap((id) => byId.get(id) ?? [])}
        labels={labels}
        relabel={queue === "relabel"}
        remaining={remaining}
        onOpen={open}
      />
    </Page>
  );
}
