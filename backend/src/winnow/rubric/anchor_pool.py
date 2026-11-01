"""The anchor pool: exactly the Dev set. Every number the Describe page shows, and every range
compile shows Spark, comes from it alone, so Rubric writing never sees the Test set."""

from pydantic import BaseModel

from winnow.core.context import AppContext
from winnow.episodes.models import Episode
from winnow.reference_labels.gate import revealed_ids
from winnow.sets.models import SetName


class AnchorPool(BaseModel):
    set_name: SetName  # always "dev"
    episode_ids: list[str]
    hidden_test_episodes: int  # the Test set, kept out of Rubric writing
    # Anchor Episodes with no Reference label yet: blind, so no Describe-page number uses them.
    awaiting_reference_label: int


def anchor_pool(ctx: AppContext) -> AnchorPool:
    ids = ctx.sets.get("dev").episode_ids
    revealed = revealed_ids(ctx)
    return AnchorPool(
        set_name="dev",
        episode_ids=ids,
        hidden_test_episodes=ctx.sets.get("test").size,
        awaiting_reference_label=sum(1 for id_ in ids if id_ not in revealed),
    )


def anchor_episodes(ctx: AppContext) -> list[Episode]:
    ids = set(anchor_pool(ctx).episode_ids)
    return [e for e in ctx.episodes.list() if e.id in ids]
