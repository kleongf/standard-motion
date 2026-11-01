"""The interview's last questions: per Phrase, the anchor Episode where its Criteria disagree most.

A Phrase's Criteria disagree on an Episode when one fails crisply while another passes crisply,
or when a fail is unconfirmed (its primitive can't fail the Phrase on its own). Most disagreeing
means a crisp fail beside a crisp pass before an unconfirmed fail alone, then the most Criteria
taking a side, then the result nearest its threshold, in effective margins. Each Phrase is asked
about at most once, and never on an Episode with a label in force on that Phrase. Pure: the
service reads the draft scored on the anchor pool and the labels.
"""

import math
from collections.abc import Sequence, Set
from dataclasses import dataclass

from winnow.criteria.models import Criterion
from winnow.interview.anchor import AnchorTriage, result_clip
from winnow.interview.models import (
    Clip,
    DisagreeQuestion,
    DisagreeResult,
    StoredAnswer,
    disagree_key,
)
from winnow.interview.wording import disagree_measurement, disagree_options, disagree_prompt
from winnow.rubric.models import DraftPhrase, RubricDraft
from winnow.triage.models import CriterionResult


@dataclass(frozen=True)
class _Disagreement:
    episode: AnchorTriage
    results: list[CriterionResult]  # the Phrase's Criteria switched on, in Rubric order
    fails: list[CriterionResult]  # crisp
    unconfirmed: list[CriterionResult]
    passes: list[CriterionResult]

    @property
    def sides(self) -> list[CriterionResult]:
        """The results that take a side, fails first."""
        return [*self.fails, *self.unconfirmed, *self.passes]

    @property
    def crisp(self) -> bool:
        return bool(self.fails and self.passes)

    @property
    def rank(self) -> tuple[bool, int, float]:
        """Lowest first: crisp, then the most Criteria taking a side, then the nearest margin."""
        return not self.crisp, -len(self.sides), min(_margins_off(r) for r in self.sides)


def _margins_off(result: CriterionResult) -> float:
    """How far the value sits from the threshold, in effective margins; inf with no margin."""
    if result.value is None or result.margin <= 0:
        return math.inf
    return abs(result.value - result.threshold) / result.margin


def _unconfirmed(result: CriterionResult) -> bool:
    return result.uncertainty == "unconfirmed fail"


def _disagreement(episode: AnchorTriage, ids: Set[str]) -> _Disagreement | None:
    results = [r for r in episode.triage.criteria if r.criterion_id in ids]
    fails = [r for r in results if r.status == "fail" and r.uncertainty is None]
    unconfirmed = [r for r in results if _unconfirmed(r)]
    passes = [r for r in results if r.status == "pass" and r.uncertainty is None]
    if not (fails and passes) and not unconfirmed:
        return None
    return _Disagreement(episode, results, fails, unconfirmed, passes)


def _most_disagreeing(
    phrase: DraftPhrase,
    criteria: Sequence[Criterion],
    triaged: Sequence[AnchorTriage],
    labelled: Set[tuple[str, str]],
) -> _Disagreement | None:
    """The Episode where the Phrase's Criteria disagree most, among those it has no label on."""
    ids = {c.id for c in criteria if c.phrase == phrase.text}
    found = [
        d
        for e in triaged
        if (e.episode_id, phrase.text) not in labelled and (d := _disagreement(e, ids)) is not None
    ]
    return min(found, key=lambda d: d.rank, default=None)


def _clip(d: _Disagreement) -> Clip:
    """Spans what every Criterion taking a side measured."""
    clips = [result_clip(r, d.episode.duration) for r in d.sides]
    return Clip(start=min(c.start for c in clips), end=max(c.end for c in clips))


def _question(phrase: DraftPhrase, d: _Disagreement) -> DisagreeQuestion:
    return DisagreeQuestion(
        key=disagree_key(phrase.start),
        prompt=disagree_prompt(phrase.text, crisp=d.crisp),
        options=disagree_options(phrase.text),
        phrase=phrase.text,
        episode_id=d.episode.episode_id,
        measurement=disagree_measurement(len(d.fails) + len(d.unconfirmed), len(d.passes)),
        camera=d.episode.camera_for(d.sides[0]),
        clip=_clip(d),
        results=[
            DisagreeResult(
                criterion_id=r.criterion_id,
                english=r.english,
                status=r.status,
                measurement=r.measurement,
                unconfirmed=_unconfirmed(r),
            )
            for r in d.results
        ],
    )


def disagree_questions(
    draft: RubricDraft,
    triaged: Sequence[AnchorTriage],
    labelled: Set[tuple[str, str]],
    answers: Sequence[StoredAnswer],
) -> list[DisagreeQuestion]:
    """One question per Phrase not yet asked about whose Criteria disagree on an anchor Episode
    it has no label on (`labelled` holds (Episode id, Phrase) pairs), most disagreeing first."""
    asked = {a.key for a in answers if a.kind == "disagree"}
    switched_on = [c for c in draft.criteria if c.id not in draft.disabled]
    found: list[tuple[DraftPhrase, _Disagreement]] = []
    for phrase in draft.phrases:
        if disagree_key(phrase.start) in asked:
            continue
        most = _most_disagreeing(phrase, switched_on, triaged, labelled)
        if most is not None:
            found.append((phrase, most))
    return [_question(p, d) for p, d in sorted(found, key=lambda pd: pd[1].rank)]
