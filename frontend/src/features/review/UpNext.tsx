// The strip under the Review Workstation: the rest of the queue in order, each opening on click.
import { frame0Url } from "../boxes/useBoxes";
import type { Episode } from "../episodes/useEpisodes";
import type { ReviewItem } from "./useReview";

const SHOWN = 12;

export function UpNext(props: {
  items: ReviewItem[];
  episodes: Map<string, Episode>;
  onOpen: (id: string) => void;
}) {
  const { items } = props;
  return (
    <section aria-label="Up next" className="mt-6">
      <div className="mb-2 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
        Up next
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nothing else needs review.</p>
      ) : (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {items.slice(0, SHOWN).map((item) => {
            const camera = props.episodes.get(item.episode_id)?.cameras[0];
            return (
              <button
                key={item.episode_id}
                type="button"
                onClick={() => {
                  props.onOpen(item.episode_id);
                }}
                className="w-36 shrink-0 rounded p-1 text-left text-xs hover:bg-muted"
              >
                {camera ? (
                  <img
                    src={frame0Url(item.episode_id, camera)}
                    alt=""
                    className="aspect-video w-full rounded bg-black object-cover"
                  />
                ) : (
                  <div className="aspect-video w-full rounded bg-muted" />
                )}
                <div className="mt-1 font-medium">{item.episode_id}</div>
                <div className="text-muted-foreground">
                  Confidence{" "}
                  <span className="tabular-nums" data-testid="up-next-confidence">
                    {item.confidence.toFixed(2)}
                  </span>
                </div>
              </button>
            );
          })}
          {items.length > SHOWN && (
            <span className="self-center px-2 text-xs text-muted-foreground">
              +{items.length - SHOWN} more
            </span>
          )}
        </div>
      )}
    </section>
  );
}
