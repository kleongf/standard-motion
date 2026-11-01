"""Asking a Rubric version's visual Criteria of the Dataset's Episodes, and the draft's of the
anchor pool (its dry run), in the background."""

from pathlib import Path

from winnow.core.context import AppContext
from winnow.criteria.models import Criterion
from winnow.rubric.anchor_pool import anchor_episodes
from winnow.rubric.models import RubricDraft, RubricVersion
from winnow.triage.reason_service import queue_reasons
from winnow.visual.crop import clips_folder
from winnow.visual.keys import ask_key
from winnow.visual.steps import draft_item_ask, draft_visual_items, visual_items

DRY_RUN = "visual-dry-run"


class MetaUnavailableError(RuntimeError):
    pass


def ask_visual(
    ctx: AppContext, version: RubricVersion, episode_ids: list[str] | None = None
) -> int | None:
    """Queues the crop and visual steps for every visual Criterion of `version` on each Episode
    (every ingested one by default); returns the job's id, or None when there's nothing to
    ask. Asking again pays only for what the Meta cache hasn't seen. Once the answers are in,
    Spark's Reasons are queued for the Episodes they changed."""
    if ctx.meta is None:
        raise MetaUnavailableError("Asking Spark needs the Meta API: set MODEL_API_KEY in .env")
    ids = episode_ids if episode_ids is not None else [e.id for e in ctx.episodes.list()]
    items = visual_items(version, ids)
    if not items:
        return None
    return ctx.runner.submit("visual", items, then=lambda: queue_reasons(ctx))


def _unasked(ctx: AppContext, draft: RubricDraft) -> list[tuple[str, Criterion]]:
    """Each anchor Episode and switched-on visual Criterion of the draft with nothing stored
    for its ask key, no answer and no error, and no dry run asking it already."""
    visual = [c for c in draft.rubric().criteria if c.kind == "visual"]
    if not visual:
        return []
    asking = {draft_item_ask(args) for args in ctx.jobs.in_flight(DRY_RUN)}
    unasked: list[tuple[str, Criterion]] = []
    for episode in anchor_episodes(ctx):
        for criterion in visual:
            key = ask_key(criterion, draft.settings)
            found = ctx.visual.get(episode.id, key)
            answered = found is not None and (found.samples or found.error is not None)
            if not answered and (episode.id, key) not in asking:
                unasked.append((episode.id, criterion))
    return unasked


def dry_run(ctx: AppContext, draft: RubricDraft) -> int | None:
    """Asks Spark, in the background, the draft's visual Criteria that the anchor pool has no
    answers to yet, so the Describe page's preview shows their pass rates before Run. Returns
    the job's id, or None without the Meta API, with the Meta budget spent, or when there's
    nothing to ask. Must be called with an event loop running, as from a route."""
    costs = None if ctx.meta is None else ctx.meta.costs
    if costs is None or costs.spent_usd() >= costs.budget_usd:
        return None  # over budget, every item would fail again: it stays not asked
    items = draft_visual_items(draft, _unasked(ctx, draft))
    return ctx.runner.submit(DRY_RUN, items) if items else None


def visual_clip(ctx: AppContext, episode_id: str, name: str) -> Path | None:
    episode = ctx.episodes.get(episode_id)
    if episode is None:
        return None
    path = clips_folder(ctx.episodes.episode_folder(episode)) / name
    return path if path.is_file() else None
