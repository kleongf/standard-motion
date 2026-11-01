"""Risk–coverage: rank the labelled Episodes by a system's confidence and, covering more of them
at each step, count how many it gets wrong. Every Episode is ranked, abstentions too, by the side
it leans to, so the two curves span the same Episodes."""

from collections.abc import Callable, Sequence
from itertools import groupby

from winnow.evaluation.cases import EvaluationCase, Ranking
from winnow.evaluation.models import (
    SYSTEM_LABELS,
    MatchedCoverage,
    MatchedRow,
    RiskCoverage,
    RiskPoint,
    System,
)
from winnow.evaluation.stats import wilson

RANKINGS: dict[System, Callable[[EvaluationCase], Ranking]] = {
    "winnow": lambda c: c.winnow_ranking,
    "spark_alone": lambda c: c.spark_alone_ranking,
}


def _wrong(case: EvaluationCase, ranking: Ranking) -> bool:
    return (ranking.lean == "reject") != case.description_failure


def ranked(cases: Sequence[EvaluationCase], system: System) -> list[list[EvaluationCase]]:
    """The cases most confident first, in groups of equal confidence (and tiebreak)."""

    def key(case: EvaluationCase) -> tuple[float, float]:
        ranking = RANKINGS[system](case)
        return (ranking.confidence, ranking.tiebreak)

    ordered = sorted(cases, key=key, reverse=True)
    return [list(group) for _, group in groupby(ordered, key=key)]


def curve(cases: Sequence[EvaluationCase], system: System) -> RiskCoverage:
    points: list[RiskPoint] = []
    covered = errors = 0
    for group in ranked(cases, system):
        covered += len(group)
        errors += sum(_wrong(c, RANKINGS[system](c)) for c in group)
        confidence = RANKINGS[system](group[0]).confidence
        points.append(RiskPoint(confidence=confidence, covered=covered, errors=errors))
    return RiskCoverage(
        system=system, label=SYSTEM_LABELS[system], episodes=len(cases), points=points
    )


def risk_coverage(cases: Sequence[EvaluationCase]) -> list[RiskCoverage]:
    return [curve(cases, system) for system in RANKINGS]


def _matched_row(system: System, kept: Sequence[EvaluationCase], covered: int) -> MatchedRow:
    meeting = sum(not c.description_failure for c in kept)
    return MatchedRow(
        system=system,
        label=SYSTEM_LABELS[system],
        covered=covered,
        keep_precision=wilson(meeting, len(kept)),
    )


def matched_coverage(cases: Sequence[EvaluationCase]) -> MatchedCoverage:
    """Winnow's Keeps at its own coverage, against Spark alone's Keeps among its most confident
    Episodes up to that many."""
    target = sum(c.winnow != "needs_review" for c in cases)
    covered: list[EvaluationCase] = []
    for group in ranked(cases, "spark_alone"):
        if len(covered) + len(group) > target:
            break
        covered += group
    spark_kept = [c for c in covered if c.spark_alone_ranking.lean == "keep"]
    return MatchedCoverage(
        target=target,
        episodes=len(cases),
        rows=[
            _matched_row("winnow", [c for c in cases if c.winnow == "keep"], target),
            _matched_row("spark_alone", spark_kept, len(covered)),
        ],
    )
