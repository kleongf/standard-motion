// Where an Episode's outputs would show before it has a Reference label: the server withholds
// them until then, so labels stay blind. Each place says how to give that label.
import { Button } from "@/components/ui/button";

import { NextStep } from "../core/NextStep";
import { goTo } from "../core/pages";
import { useEpisodes } from "../episodes/useEpisodes";
import { setsByEpisode, useSets } from "../sets/useSets";

export function AwaitingLabelTag() {
  return (
    <span
      data-testid="awaiting-label"
      className="text-xs whitespace-nowrap text-muted-foreground italic"
    >
      Awaiting Reference label
    </span>
  );
}

/** The Workstation panel's note, with a button that opens this Episode in Reference labels. */
export function AwaitingLabelNote(props: { episodeId: string }) {
  const set = setsByEpisode(useSets().data).get(props.episodeId);
  return (
    <section aria-label="Triage" className="grid gap-2">
      <AwaitingLabelTag />
      <p className="text-sm text-muted-foreground">
        Its Triage decision, Reason and Criterion results stay hidden until it has a Reference
        label, so that label is given blind.
      </p>
      <Button
        size="sm"
        className="justify-self-start"
        onClick={() => {
          goTo("reference", { episode: props.episodeId, queue: set ?? null });
        }}
      >
        Label this Episode
      </Button>
    </section>
  );
}

/** Above the Episodes table: how many show no results yet, and where to label them. */
export function AwaitingLabelBanner() {
  const episodes = useEpisodes().data ?? [];
  const waiting = episodes.filter((e) => !e.reference_labelled).length;
  if (waiting === 0) return null;
  return (
    <NextStep
      page="reference"
      action={`Label ${String(waiting)} Episode${waiting === 1 ? "" : "s"}`}
    >
      An Episode shows no results until it has a Reference label, given blind.
    </NextStep>
  );
}
