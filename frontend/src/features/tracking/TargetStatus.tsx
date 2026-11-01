// The Workstation panel's line for the target box: who found it, or why there is none. Nothing
// before the Episode is boxed, or while blind.
import { describeTarget } from "./describeTarget";
import { useTargetBox } from "./useTargetBoxes";

export function TargetStatus(props: { episodeId: string; hidden?: boolean | undefined }) {
  const target = useTargetBox(props.episodeId, props.hidden);
  if (!target) return null;
  const { text, missing } = describeTarget(target);
  return (
    <>
      <dt className="text-muted-foreground">Target box</dt>
      <dd
        data-testid="target-status"
        className={missing ? "text-amber-700 dark:text-amber-400" : undefined}
      >
        {text}
      </dd>
    </>
  );
}
