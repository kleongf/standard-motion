"""Saving a label against the latest Rubric version (Review, Audit) or the Rubric draft (the
interview)."""

from datetime import UTC, datetime

from standard_motion.core.context import AppContext
from standard_motion.labels.models import LabelDraw, StoredLabel
from standard_motion.triage.reason_service import queue_reasons


class UnknownPhraseError(ValueError):
    pass


def _stored(draw: LabelDraw, episode_id: str, rubric_version: int | None) -> StoredLabel:
    return StoredLabel(
        **draw.model_dump(),
        episode_id=episode_id,
        rubric_version=rubric_version,
        labelled_at=datetime.now(UTC).isoformat(),
    )


def save_label(ctx: AppContext, episode_id: str, draw: LabelDraw) -> StoredLabel:
    """Raises UnknownPhraseError unless `draw` names a Phrase of the latest Rubric version. A
    review label recomputes the Episode's Triage decision, so with the Meta API, Spark's Reasons
    it put out of date are queued in the background; an audit label changes no result."""
    version = ctx.rubrics.latest()
    if draw.phrase not in version.rubric.phrases:
        raise UnknownPhraseError(f"{draw.phrase!r} isn't a Phrase of Rubric v{version.version}")
    saved = ctx.labels.add(_stored(draw, episode_id, version.version))
    if draw.source == "review":
        queue_reasons(ctx)
    return saved


def save_draft_label(ctx: AppContext, episode_id: str, draw: LabelDraw) -> StoredLabel:
    """Raises UnknownPhraseError unless `draw` names a Phrase of the Rubric draft."""
    draft = ctx.drafts.get()
    if draft is None or draw.phrase not in (p.text for p in draft.phrases):
        raise UnknownPhraseError(f"{draw.phrase!r} isn't a Phrase of the Rubric draft")
    return ctx.labels.add(_stored(draw, episode_id, None))
