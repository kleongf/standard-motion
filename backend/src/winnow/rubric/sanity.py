"""The Rubric sanity monitor: a warning about the Rubric, never about one Episode.

For each hard Criterion it reads the anchor pool's fail rate (with its Wilson interval), warns
when the rate is below 2% (the Criterion rejects almost nothing) or above 95% (almost everything),
and lists the Episodes only that Criterion rejects, so the curator sees what it removes. It reads
the same Dev set, labels and margin multiplier s as the preview it extends.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.models import Criterion
from winnow.evaluation.stats import Proportion, wilson
from winnow.rubric.models import Rubric, SanityWarning
from winnow.triage.models import CriterionResult, Label
from winnow.triage.scoring import score

TOO_RARE = 0.02
TOO_COMMON = 0.95


@dataclass(frozen=True)
class Sanity:
    fail_rate: Proportion
    warning: SanityWarning | None
    only_rejects: list[str]


def warning_for(fail_rate: Proportion) -> SanityWarning | None:
    """Judged on the observed rate: the interval is shown beside it, not folded into it."""
    if fail_rate.of == 0:
        return None
    rate = fail_rate.count / fail_rate.of
    if rate < TOO_RARE:
        return "too_rare"
    return "too_common" if rate > TOO_COMMON else None


def only_rejects(
    rubric: Rubric,
    criterion: Criterion,
    rejected: Mapping[str, EpisodeFacts],
    labels: Mapping[str, Sequence[Label]],
    s: float,
) -> list[str]:
    """Of the `rejected` Episodes, those no longer Rejected with `criterion` removed and
    everything else equal: the same labels and margin multiplier s."""
    without = rubric.model_copy(
        update={"criteria": [c for c in rubric.criteria if c.id != criterion.id]}
    )
    return [
        id_
        for id_, facts in rejected.items()
        if score(without, facts, labels.get(id_, ()), s).decision != "reject"
    ]


def sanity(
    rubric: Rubric,
    shown: Sequence[Criterion],
    rejected: Mapping[str, EpisodeFacts],
    results: Mapping[str, Mapping[str, CriterionResult]],
    labels: Mapping[str, Sequence[Label]],
    s: float,
) -> dict[str, Sanity]:
    """The reading of each `shown` hard Criterion that `rubric` scores, by id. `rejected` are
    the facts of the Episodes the Rubric Rejects, `results` the shown Criteria's results per
    Episode. Only an Episode a Criterion fails can be rejected by it alone, which keeps a label's
    Reject from being listed under a Criterion that passes: removing that Criterion would lift
    the label's Reject too (a Phrase with no hard Criterion ignores its label)."""
    in_rubric = {c.id for c in rubric.criteria}
    readings: dict[str, Sanity] = {}
    for criterion in shown:
        if not criterion.hard or criterion.id not in in_rubric:
            continue
        fails = [found[criterion.id].status for found in results.values()].count("fail")
        rate = wilson(fails, len(results))
        failed = {
            id_: f for id_, f in rejected.items() if results[id_][criterion.id].status == "fail"
        }
        readings[criterion.id] = Sanity(
            rate, warning_for(rate), only_rejects(rubric, criterion, failed, labels, s)
        )
    return readings
