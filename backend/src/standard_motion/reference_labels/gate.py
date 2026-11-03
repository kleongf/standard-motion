"""The blind gate. Until an Episode has a first-pass Reference label (a relabel doesn't count),
its Standard Motion and Spark-alone outputs (Triage decision, Reason, Criterion and Phrase results,
confidence, baseline answers) and its Dataset outcome stay out of every response the app reads,
so labels are given blind.

Every route serving a per-Episode output goes through here: one Episode's output takes a
`RevealedEpisode` (403 until labelled), a list of outputs reads only `revealed_episodes(ctx)`.
Episode facts (video, robot data, object tracks) aren't outputs and stay visible.

The export is the one exception: it writes every Episode outside the Test set by its Triage
decision (export/plan.py), after the UI says how many aren't labelled yet."""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, status

from standard_motion.core.context import AppContext, get_context
from standard_motion.episodes.models import Episode


def revealed_ids(ctx: AppContext) -> set[str]:
    return ctx.reference_labels.labelled_ids()


def listed_episodes(ctx: AppContext) -> list[Episode]:
    """Every Episode as the app lists it: which are labelled, and the Dataset outcome only for
    those."""
    revealed = revealed_ids(ctx)
    return [
        e.model_copy(update={"reference_labelled": True})
        if e.id in revealed
        else e.model_copy(update={"reference_labelled": False, "dataset_outcome": None})
        for e in ctx.episodes.list()
    ]


def revealed_episodes(ctx: AppContext) -> list[Episode]:
    """The Episodes whose outputs may be shown."""
    revealed = revealed_ids(ctx)
    return [e for e in ctx.episodes.list() if e.id in revealed]


async def revealed_episode(
    episode_id: str, ctx: Annotated[AppContext, Depends(get_context)]
) -> Episode:
    episode = ctx.episodes.get(episode_id)
    if episode is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"No Episode {episode_id}"
        )
    if episode_id not in revealed_ids(ctx):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{episode_id} has no Reference label yet, so its outputs stay hidden",
        )
    return episode


# The 403 a route taking a `RevealedEpisode` adds to its OpenAPI responses.
HIDDEN_UNTIL_LABELLED: dict[int | str, dict[str, Any]] = {
    403: {"description": "The Episode has no Reference label yet"}
}

# A path parameter `episode_id` resolved to its Episode, only once it has a Reference label.
RevealedEpisode = Annotated[Episode, Depends(revealed_episode)]
