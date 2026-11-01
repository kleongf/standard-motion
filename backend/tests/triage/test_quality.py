"""The quality score: each soft Criterion's robust z within the run (median and MAD), signed so
higher is better, averaged per Episode. It ranks Episodes; it never decides one."""

from itertools import combinations, product

import pytest

from tests.triage.robot_data import (
    CLEAN_GRIPPER,
    CLEAN_Z,
    PLACES,
    REGRASP_GRIPPER,
    REGRASP_Z,
    facts,
    first_try,
    release,
    rubric,
    still,
)
from winnow.criteria.models import Comparator
from winnow.triage.models import CriterionResult, Label, Triage
from winnow.triage.quality import qualities
from winnow.triage.scoring import score

_SCORED = score(rubric(first_try(), still(hard=False, id="pause")), facts(CLEAN_GRIPPER, CLEAN_Z))
_HARD, _SOFT = _SCORED.criteria


def soft(
    value: float | None, comparator: Comparator = "<", threshold: float = 1.0, id: str = "pause"
) -> CriterionResult:
    return _SOFT.model_copy(
        update={
            "criterion_id": id,
            "value": value,
            "comparator": comparator,
            "threshold": threshold,
        }
    )


def triage(*results: CriterionResult) -> Triage:
    return _SCORED.model_copy(update={"criteria": [_HARD, *results]})


def test_quality_is_the_robust_z_of_a_soft_value_against_the_runs_median_and_mad():
    # Shorter pauses are better under "<". Median 3 s, MAD 1 s: z = (3 - v) / 1.4826.
    triages = [triage(soft(v)) for v in (1, 2, 3, 4, 5)]

    assert qualities(triages) == pytest.approx([1.349, 0.674, 0.0, -0.674, -1.349], abs=1e-3)


def test_a_soft_criterion_whose_values_barely_vary_is_skipped_mad_zero():
    # Three of four Episodes pause 2 s: the MAD is 0, so the pauses say nothing about quality.
    triages = [triage(soft(v)) for v in (2, 2, 2, 5)]

    assert qualities(triages) == [None, None, None, None]


def test_an_episodes_quality_is_the_mean_of_its_soft_zs_skipping_missing_values():
    # Pauses: median 2, MAD 1, z = (2 - v) / 1.4826. Height: median 3, MAD 1, z = (h - 3) / 1.4826.
    pauses = (1, 2, 3, None)
    heights = (4, 3, None, 2)
    triages = [
        triage(soft(p), soft(h, comparator=">=", threshold=0, id="height"))
        for p, h in zip(pauses, heights, strict=True)
    ]

    assert qualities(triages) == pytest.approx([0.674, 0.0, -0.674, -0.674], abs=1e-3)
    assert qualities([triage(), triage(soft(None))]) == [None, None]  # nothing soft to compare


@pytest.mark.parametrize(
    ("comparator", "expected"),
    [
        ("<", [1.349, 0.674, 0.0, -0.674, -1.349]),  # lower is better
        ("<=", [1.349, 0.674, 0.0, -0.674, -1.349]),
        (">", [-1.349, -0.674, 0.0, 0.674, 1.349]),  # higher is better
        (">=", [-1.349, -0.674, 0.0, 0.674, 1.349]),
    ],
)
def test_quality_is_signed_so_the_passing_side_scores_higher(
    comparator: Comparator, expected: list[float]
):
    triages = [triage(soft(v, comparator, threshold=3)) for v in (1, 2, 3, 4, 5)]

    assert qualities(triages) == pytest.approx(expected, abs=1e-3)


def test_under_equals_closer_to_the_threshold_scores_higher():
    # Distances from 3: 2, 1, 0, 1, 2. Median 1, MAD 1: z = (1 - distance) / 1.4826.
    triages = [triage(soft(v, "==", threshold=3)) for v in (1, 2, 3, 4, 5)]

    assert qualities(triages) == pytest.approx([-0.674, 0.0, 0.674, 0.0, -0.674], abs=1e-3)


HARD = [first_try(), still(), release()]
SOFT = [
    first_try(threshold=0, hard=False, id="soft-attempts"),
    still(phrase=PLACES, hard=False, id="soft-pause", threshold=0.1),
    release(threshold=0.01).model_copy(update={"id": "soft-release", "hard": False}),
]
EPISODES = [facts(CLEAN_GRIPPER, CLEAN_Z), facts(REGRASP_GRIPPER, REGRASP_Z)]
# The clean Episode's 10 cm release fails inconclusively, so it needs review until a label
# passes its Phrase; the regrasp is rejected either way.
LABELS: list[list[Label]] = [[], [Label(phrase=PLACES, value="pass", source="review")]]


def test_adding_or_removing_soft_criteria_never_changes_a_triage_decision():
    for episode, labels in product(EPISODES, LABELS):
        without = score(rubric(*HARD), episode, labels)
        for n in range(1, len(SOFT) + 1):
            for soft_criteria in combinations(SOFT, n):
                with_soft = score(rubric(*HARD, *soft_criteria), episode, labels)

                assert (with_soft.decision, with_soft.p_keep) == (without.decision, without.p_keep)
    # The sample covers every decision, so the check isn't vacuous.
    decisions = {score(rubric(*HARD), e, ls).decision for e, ls in product(EPISODES, LABELS)}
    assert decisions == {"keep", "reject", "needs_review"}
