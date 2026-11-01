// Review: the Needs review queue, strictly least confident first. The Workstation shows one
// Episode with "Your call" in its actions slot; an answer that decides the Episode takes it out
// of the queue and the next least confident one opens. `?episode=` picks another from Up next.
import { Page, PageHeader } from "../core/PageHeader";
import { navigate, useSearchParams } from "../core/url";
import { useEpisodes, type Episode } from "../episodes/useEpisodes";
import { Workstation } from "../episodes/Workstation";
import { useSaveLabel } from "../labels/useLabels";
import { VoicePanel } from "../voice/VoicePanel";
import { UpNext } from "./UpNext";
import { useReviewQueue, type ReviewItem } from "./useReview";
import { YourCall, type Answer } from "./YourCall";

export function ReviewPage() {
  const params = useSearchParams();
  const queue = useReviewQueue();
  const episodes = new Map((useEpisodes().data ?? []).map((e) => [e.id, e]));
  const items = queue.data?.items ?? [];
  const current = items.find((i) => i.episode_id === params.get("episode")) ?? items[0];
  const episode = current && episodes.get(current.episode_id);

  return (
    <Page width="full">
      <ReviewHeader reviewed={queue.data?.reviewed ?? 0} left={items.length} current={current} />
      {current ? (
        <>
          {episode && (
            // Keyed so each Episode starts with its own playhead, focus and save state.
            <ReviewWorkstation key={episode.id} item={current} episode={episode} />
          )}
          <UpNext
            items={items.filter((i) => i !== current)}
            episodes={episodes}
            onOpen={(id) => {
              navigate({ episode: id, t: null });
            }}
          />
        </>
      ) : (
        <QueueStatus queue={queue} />
      )}
    </Page>
  );
}

/** What shows without an Episode to review: loading, an error, or an empty queue. */
function QueueStatus(props: { queue: ReturnType<typeof useReviewQueue> }) {
  const { queue } = props;
  if (queue.isPending) return <p className="text-sm text-muted-foreground">Loading the queue…</p>;
  if (queue.isError) return <p className="text-sm text-destructive">{queue.error.message}</p>;
  return (
    <p className="text-sm text-muted-foreground">
      The queue is empty: every Episode with a Reference label is decided.
    </p>
  );
}

function ReviewHeader(props: { reviewed: number; left: number; current: ReviewItem | undefined }) {
  const { reviewed, current } = props;
  const total = reviewed + props.left;
  return (
    <PageHeader
      title="Review"
      subtitle={`${String(reviewed)} of ${String(total)} reviewed · least confident first`}
      progress={total > 0 ? reviewed / total : undefined}
      actions={
        current && (
          <span className="text-sm font-medium tabular-nums" data-testid="review-current">
            {current.episode_id}
          </span>
        )
      }
    />
  );
}

/** The Workstation with "Your call" and Voice in its actions slot; each answer, clicked, keyed
 * or spoken and confirmed, is a `review` label. */
function ReviewWorkstation(props: { item: ReviewItem; episode: Episode }) {
  const { item, episode } = props;
  const save = useSaveLabel();
  const answer = (phrase: string, value: Answer) => {
    save.mutate({ episodeId: item.episode_id, draw: { phrase, value, source: "review" } });
  };
  return (
    <Workstation
      episode={episode}
      actions={(playhead) => (
        <>
          <YourCall item={item} pending={save.isPending} onAnswer={answer} />
          {save.isError && <p className="-mt-2 text-xs text-destructive">{save.error.message}</p>}
          <VoicePanel
            episodeId={item.episode_id}
            unsure={item.unsure.map((u) => u.phrase)}
            playhead={playhead}
            saving={save.isPending}
            onConfirm={answer}
          />
        </>
      )}
    />
  );
}
