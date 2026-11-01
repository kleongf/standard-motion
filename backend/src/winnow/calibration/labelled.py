"""What calibration reads off the labelled anchor Episodes, scored with no label applied: each
labelled (Episode, Phrase) pair's errors at every s of the grid, and the thresholds labels
suggest. Pure: the service gathers the Episodes' facts and labels.

A threshold is suggested where two or more labels contradict a hard Criterion's crisp result,
by the interview's bracketing: midway between the closest labelled pass and fail values, with
their gap as its margin. Labels that overlap (a pass beyond a fail) suggest nothing, since no
threshold sorts them. A fail label that another Criterion of the Phrase already explains (it
fails the Phrase conclusively) says nothing about this one, so it is left out.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from winnow.calibration.models import ThresholdSuggestion
from winnow.calibration.scan import GRID, Pattern
from winnow.criteria.english import english
from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.models import Criterion
from winnow.interview.bisection import Answered, resolve, separated
from winnow.rubric.models import Rubric
from winnow.triage.models import CriterionResult, Label, PhraseResult, Triage
from winnow.triage.scoring import score

MIN_CONTRADICTING = 2


@dataclass(frozen=True)
class LabelledEpisode:
    episode_id: str
    facts: EpisodeFacts
    labels: Sequence[Label]  # the interview and review labels in force on it


def _phrase(triage: Triage, phrase: str) -> PhraseResult:
    return next(p for p in triage.phrases if p.phrase == phrase)


def _crisp(status: str | None) -> bool:
    return status in ("pass", "fail")


def _wrong(phrase: PhraseResult, label: Label) -> bool:
    """A crisp Phrase result its label contradicts; unsure is never wrong."""
    return _crisp(phrase.status) and phrase.status != label.value


def patterns(rubric: Rubric, episodes: Sequence[LabelledEpisode]) -> list[Pattern]:
    """One per label on a Phrase of `rubric` that a Criterion checks, in order."""
    found: list[Pattern] = []
    for episode in episodes:
        by_s = [score(rubric, episode.facts, (), s) for s in GRID]
        for label in episode.labels:
            if label.phrase not in rubric.phrases:
                continue  # given against another Rubric version's Phrases
            phrases = [_phrase(triage, label.phrase) for triage in by_s]
            if phrases[0].status is not None:  # whether anything checks it doesn't depend on s
                found.append(tuple(_wrong(p, label) for p in phrases))
    return found


@dataclass(frozen=True)
class _Point:
    value: float
    fine: bool  # labelled pass
    contradicts: bool


def _point(result: CriterionResult, phrase: PhraseResult, label: Label) -> _Point | None:
    if result.value is None:
        return None
    fine = label.value == "pass"
    if not fine and result.status != "fail" and phrase.status == "fail":
        return None  # another Criterion fails the Phrase, as labelled
    contradicts = _crisp(result.status) and (result.status == "pass") != fine
    return _Point(result.value, fine, contradicts)


def _points(criterion: Criterion, scored: Sequence[tuple[LabelledEpisode, Triage]]) -> list[_Point]:
    found: list[_Point] = []
    for episode, triage in scored:
        label = next((x for x in episode.labels if x.phrase == criterion.phrase), None)
        if label is None:
            continue
        result = next(r for r in triage.criteria if r.criterion_id == criterion.id)
        point = _point(result, _phrase(triage, criterion.phrase), label)
        if point is not None:
            found.append(point)
    return found


def _suggestable(criterion: Criterion) -> bool:
    """A hard threshold the interview could bisect: not a visual Criterion, not `==`."""
    return criterion.hard and criterion.kind != "visual" and criterion.comparator != "=="


def _suggestion(criterion: Criterion, points: list[_Point]) -> ThresholdSuggestion | None:
    contradicting = sum(p.contradicts for p in points)
    if contradicting < MIN_CONTRADICTING:
        return None
    asked = [Answered("", p.value, p.fine) for p in points]
    if not separated(asked, criterion.comparator):
        return None  # the labels overlap: no threshold sorts them, so none is suggested
    resolution = resolve(asked, criterion.threshold, criterion.comparator)
    if resolution.outcome != "set" or resolution.margin is None:
        return None  # labelled on one side only: nothing shows where the line is
    moved = criterion.model_copy(update={"threshold": resolution.threshold})
    return ThresholdSuggestion(
        criterion_id=criterion.id,
        phrase=criterion.phrase,
        english=english(criterion),
        suggested_english=english(moved),
        threshold=criterion.threshold,
        unit=criterion.unit,
        suggested_threshold=resolution.threshold,
        suggested_margin=resolution.margin,
        contradicting=contradicting,
        labelled=len(points),
    )


def suggestions(
    rubric: Rubric, episodes: Sequence[LabelledEpisode], s: float
) -> list[ThresholdSuggestion]:
    """In Rubric order. `s` decides which results are crisp: the version's own."""
    scored = [(e, score(rubric, e.facts, (), s)) for e in episodes]
    found: list[ThresholdSuggestion] = []
    for criterion in filter(_suggestable, rubric.criteria):
        suggestion = _suggestion(criterion, _points(criterion, scored))
        if suggestion is not None:
            found.append(suggestion)
    return found
