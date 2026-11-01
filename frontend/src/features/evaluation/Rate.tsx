// A rate as the report shows it: the count first, its 95% Wilson interval under it.
import { countOf, interval } from "./reportText";
import type { Proportion } from "./useEvaluation";

export function Rate(props: { p: Proportion }) {
  const range = interval(props.p);
  return (
    <div className="tabular-nums">
      <div>{countOf(props.p)}</div>
      {range && <div className="text-xs text-muted-foreground">{range}</div>}
    </div>
  );
}
