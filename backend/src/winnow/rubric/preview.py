"""Scoring a Rubric on the anchor pool, for the Describe page's histograms and counts.

Only anchor Episodes with a Reference label take part: the rest stay blind (the gate in
`reference_labels.gate`), and no Test set Episode is ever in the anchor pool. Everything is the
pure scoring function over stored facts and the labels in force (an interview answer overrides
its Phrase like any label), so a preview makes no model call.
"""

from collections.abc import Mapping, Sequence

from winnow.core.context import AppContext
from winnow.criteria.english import english
from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.models import Criterion
from winnow.reference_labels.gate import revealed_ids
from winnow.rubric.anchor_pool import anchor_episodes
from winnow.rubric.models import (
    AnchorEpisode,
    AnchorPreview,
    AnchorValue,
    CriterionPreview,
    Rubric,
)
from winnow.rubric.sanity import Sanity, sanity
from winnow.triage.confidence import UNCALIBRATED, effective_margin
from winnow.triage.models import CriterionResult, Label, Triage
from winnow.triage.scoring import score
from winnow.triage.service import episode_facts


def revealed_anchor_facts(ctx: AppContext) -> dict[str, EpisodeFacts]:
    """The facts of each anchor Episode whose outputs may be shown, by id."""
    revealed = revealed_ids(ctx)
    return {e.id: episode_facts(ctx, e) for e in anchor_episodes(ctx) if e.id in revealed}


def anchor_labels(ctx: AppContext, ids: list[str]) -> dict[str, list[Label]]:
    """The labels in force on each anchor Episode, by id."""
    return {id_: list(ctx.labels.in_force(id_)) for id_ in ids}


def _criterion(
    criterion: Criterion,
    results: dict[str, CriterionResult],
    s: float,
    reading: Sanity | None,
) -> CriterionPreview:
    statuses = [r.status for r in results.values()]
    return CriterionPreview(
        criterion_id=criterion.id,
        english=english(criterion),
        threshold=criterion.threshold,
        margin=effective_margin(criterion, s),
        unit=criterion.unit,
        passing=statuses.count("pass"),
        failing=statuses.count("fail"),
        unsure=statuses.count("unsure"),
        values=[
            AnchorValue(episode_id=id_, value=r.value, status=r.status)
            for id_, r in results.items()
        ],
        fail_rate=reading.fail_rate if reading else None,
        warning=reading.warning if reading else None,
        only_rejects=reading.only_rejects if reading else [],
    )


def anchor_preview(
    facts: dict[str, EpisodeFacts],
    rubric: Rubric,
    shown: list[Criterion],
    version: int | None,
    labels: Mapping[str, Sequence[Label]],
    s: float = UNCALIBRATED,
) -> AnchorPreview:
    """`rubric` decides each Episode, with its `labels` and margin multiplier `s`; `shown` are
    the Criteria to histogram, a superset of the Rubric's when some are switched off."""
    everything = rubric.model_copy(update={"criteria": shown})
    triages: dict[str, Triage] = {
        id_: score(rubric, f, labels.get(id_, ()), s) for id_, f in facts.items()
    }
    results = {
        id_: {r.criterion_id: r for r in score(everything, f, (), s).criteria}
        for id_, f in facts.items()
    }
    rejected = {id_: facts[id_] for id_, t in triages.items() if t.decision == "reject"}
    readings = sanity(rubric, shown, rejected, results, labels, s)
    decisions = [t.decision for t in triages.values()]
    episodes = [
        AnchorEpisode(episode_id=id_, decision=t.decision, confidence=t.confidence)
        for id_, t in triages.items()
    ]
    return AnchorPreview(
        rubric_version=version,
        keep=decisions.count("keep"),
        reject=decisions.count("reject"),
        needs_review=decisions.count("needs_review"),
        episodes=sorted(episodes, key=lambda e: e.confidence),
        criteria=[
            _criterion(
                c, {id_: found[c.id] for id_, found in results.items()}, s, readings.get(c.id)
            )
            for c in shown
        ],
    )
