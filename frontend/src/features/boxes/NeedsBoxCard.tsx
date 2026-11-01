// One Episode in Prepare's Needs-a-box grid: its frame 0, its instruction or that the dataset
// gave none, and the object to box where the selection pass named it.
import type { Episode } from "../episodes/useEpisodes";
import { frame0Url } from "./useBoxes";

export function NeedsBoxCard(props: { episode: Episode; onOpen: () => void }) {
  const { episode } = props;
  return (
    <button
      type="button"
      className="group self-start text-left"
      aria-label={`Draw a box for Episode ${String(episode.index)}`}
      onClick={props.onOpen}
    >
      <img
        src={frame0Url(episode.id, "exterior_image_1_left")}
        alt=""
        loading="lazy"
        className="aspect-video w-full rounded border bg-muted object-cover group-hover:ring-2 group-hover:ring-primary"
      />
      <div className="mt-1 text-xs font-medium">Episode {episode.index}</div>
      {episode.task_object && <div className="truncate text-xs">Box: {episode.task_object}</div>}
      <div className="truncate text-xs text-muted-foreground">
        {episode.instruction ?? "No instruction in the dataset"}
      </div>
    </button>
  );
}
