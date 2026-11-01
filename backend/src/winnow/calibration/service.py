"""Calibrating the latest Rubric version on the anchor pool's labels, and accepting a threshold
they suggest.

Only anchor-pool Episodes with a Reference label take part (the Dev set, never the Test set),
with only their interview and review labels: audit labels measure Keep precision alone. Each is
scored with no label applied, so the labels judge Winnow's own results. Everything is the pure
scoring function over stored facts, so calibrating makes no model call; with the Meta API, the
Spark Reasons a new s or threshold puts out of date are then queued in the background.
"""

from winnow.calibration.labelled import LabelledEpisode, patterns, suggestions
from winnow.calibration.models import AcceptedSuggestion, Calibration
from winnow.calibration.scan import CONFIDENCE, GRID, MAX_ERROR_RATE, scan, unstable
from winnow.core.context import AppContext
from winnow.criteria.models import Criterion
from winnow.rubric.models import RubricDraft, RubricVersion
from winnow.rubric.preview import anchor_labels, revealed_anchor_facts
from winnow.triage.reason_service import queue_reasons


class NoLabelsError(ValueError):
    pass


class NoSuggestionError(LookupError):
    pass


def _labelled(ctx: AppContext) -> list[LabelledEpisode]:
    facts = revealed_anchor_facts(ctx)
    labels = anchor_labels(ctx, list(facts))
    return [LabelledEpisode(id_, f, labels[id_]) for id_, f in facts.items() if labels[id_]]


def _calibration(
    ctx: AppContext, version: RubricVersion, episodes: list[LabelledEpisode]
) -> Calibration:
    s = ctx.calibrations.s_for(version.version)
    return Calibration(
        rubric_version=version.version,
        s=s,
        record=ctx.calibrations.latest(version.version),
        labelled=len(patterns(version.rubric, episodes)),
        grid=list(GRID),
        max_error_rate=MAX_ERROR_RATE,
        confidence=CONFIDENCE,
        suggestions=suggestions(version.rubric, episodes, s),
    )


def calibration(ctx: AppContext) -> Calibration:
    return _calibration(ctx, ctx.rubrics.latest(), _labelled(ctx))


def calibrate(ctx: AppContext) -> Calibration:
    """Scans s for the latest Rubric version and stores it, with the leave-one-out check.
    Raises NoLabelsError when no label is on a Phrase the version checks."""
    version = ctx.rubrics.latest()
    episodes = _labelled(ctx)
    pairs = patterns(version.rubric, episodes)
    if not pairs:
        raise NoLabelsError(
            "No interview or review label on the anchor pool yet: label some Phrases first"
        )
    found = scan(pairs)
    ctx.calibrations.add(
        version.version, found.s, found.n, found.errors, found.bound_met, unstable(pairs)
    )
    queue_reasons(ctx)
    return _calibration(ctx, version, episodes)


def _settled(
    criteria: list[Criterion], criterion_id: str, changes: dict[str, object]
) -> list[Criterion]:
    return [c.model_copy(update=changes) if c.id == criterion_id else c for c in criteria]


def _same_check(a: Criterion, b: Criterion) -> bool:
    """Whether a threshold set on one means the same on the other."""
    return (a.comparator, a.primitive, a.unit) == (b.comparator, b.primitive, b.unit)


def _draft_change(
    draft: RubricDraft | None, frozen: Criterion, changes: dict[str, object]
) -> tuple[RubricDraft | None, str]:
    """The draft with the accepted threshold, or None to leave it, and what happened to it."""
    if draft is None:
        return None, "There's no Rubric draft to update."
    mine = next((c for c in draft.criteria if c.id == frozen.id), None)
    if mine is None:
        return None, f"The draft has no Criterion {frozen.id}, so it was left as it is."
    if not _same_check(mine, frozen):
        return None, (
            f"The draft's Criterion {frozen.id} now compares differently "
            "(comparator, primitive or unit changed), so it was left as it is."
        )
    criteria = _settled(draft.criteria, frozen.id, changes)
    return draft.model_copy(update={"criteria": criteria}), (
        f"The draft's Criterion {frozen.id} moved too."
    )


def accept_suggestion(ctx: AppContext, criterion_id: str) -> AcceptedSuggestion:
    """Freezes the latest Rubric version with the threshold and margin labels suggest for
    `criterion_id` as the next version, which starts at s = 1, and carries them into the draft
    so the next Run keeps them, unless the draft's Criterion now checks something else. The
    suggested value is no longer an assumption. Both writes happen together or not at all.
    Raises NoSuggestionError when labels suggest nothing for it now."""
    version = ctx.rubrics.latest()
    found = next((x for x in calibration(ctx).suggestions if x.criterion_id == criterion_id), None)
    if found is None:
        raise NoSuggestionError(
            f"Labels suggest no threshold for {criterion_id} on v{version.version}"
        )
    changes: dict[str, object] = {
        "threshold": found.suggested_threshold,
        "margin": found.suggested_margin,
        "assumptions": [],
    }
    frozen = next(c for c in version.rubric.criteria if c.id == criterion_id)
    draft, note = _draft_change(ctx.drafts.get(), frozen, changes)
    rubric = version.rubric
    criteria = _settled(rubric.criteria, criterion_id, changes)
    with ctx.db:
        ctx.db.execute("BEGIN IMMEDIATE")
        added = ctx.rubrics.add(rubric.model_copy(update={"criteria": criteria}))
        if draft is not None:
            ctx.drafts.save(draft)
    queue_reasons(ctx)
    return AcceptedSuggestion(version=added, draft_updated=draft is not None, draft_note=note)
