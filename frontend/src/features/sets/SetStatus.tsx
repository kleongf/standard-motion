// Each set's size and whether its membership is frozen. Sets are defined and frozen with
// `standard-motion sets` or the /api/sets routes.
import { SET_LABELS, useSets, type EpisodeSet } from "./useSets";

const FROZEN_FORMAT = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

export function SetStatus() {
  const sets = useSets();
  if (!sets.data) return null;
  return (
    <div className="mt-3 grid grid-cols-2 gap-3">
      {sets.data.map((s) => (
        <SetCard key={s.name} set={s} />
      ))}
    </div>
  );
}

function SetCard(props: { set: EpisodeSet }) {
  const { name, size, frozen_at: frozenAt } = props.set;
  return (
    <div className="flex items-baseline gap-2 rounded-lg border p-3" data-testid={`set-${name}`}>
      <span className="text-sm font-medium">{SET_LABELS[name]}</span>
      <span className="text-sm tabular-nums">
        {size} {size === 1 ? "Episode" : "Episodes"}
      </span>
      <span className="ml-auto text-xs text-muted-foreground">
        {frozenAt ? `frozen ${FROZEN_FORMAT.format(new Date(frozenAt))}` : "not frozen"}
      </span>
    </div>
  );
}
