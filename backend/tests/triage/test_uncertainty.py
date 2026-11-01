"""Uncertainty signals and confidence: why a result is unsure, and how sure each Episode is."""

import numpy as np
import pytest

from tests.triage.robot_data import (
    CLEAN_GRIPPER,
    CLEAN_Z,
    DOWN,
    FIRST_TRY,
    PLACES,
    REGRASP_GRIPPER,
    UP,
    facts,
    first_try,
    frames,
    release,
    rubric,
    still,
    text,
)
from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.models import Criterion, Window
from winnow.triage.models import Label
from winnow.triage.scoring import score

STRAIGHT = np.linspace(0, 0.3, 45).tolist()  # along x
# Rising steadily, so the arm lifts 3.2 cm while the gripper is closed: a clean grasp, and with
# STRAIGHT a path efficiency of exactly 1.
RISING = np.linspace(0, 0.1, 45).tolist()


def efficient(threshold: float, margin: float = 0.0, hard: bool = True) -> Criterion:
    return Criterion(
        id=f"path-{threshold}",
        phrase=PLACES,
        primitive="path_efficiency",
        comparator=">=",
        threshold=threshold,
        unit="ratio",
        margin=margin,
        hard=hard,
    )


def straight_clean_grasp() -> EpisodeFacts:
    return facts(CLEAN_GRIPPER, RISING, STRAIGHT)


def test_a_value_within_its_effective_margin_is_near_threshold_and_unsure():
    # Efficiency 1.0 against ≥ 0.9: 0.1 away. The noise floor (0.05) alone leaves it crisp; an
    # interview gap of 0.2 widens the margin past it.
    crisp = score(rubric(efficient(0.9)), straight_clean_grasp())
    near = score(rubric(efficient(0.9, margin=0.2)), straight_clean_grasp())

    assert (crisp.criteria[0].status, crisp.criteria[0].uncertainty) == ("pass", None)
    assert near.criteria[0].margin == 0.2
    assert (near.criteria[0].status, near.criteria[0].uncertainty) == ("unsure", "near threshold")
    assert near.decision == "needs_review"
    assert text(near) == f'Needs review: "{PLACES}": near threshold (1.00 against ≥ 0.90).'


def test_measured_p_is_a_logistic_in_the_signed_distance_in_effective_margins():
    # m = (1.0 - 0.9) / 0.2 = 0.5 -> p = 1/(1 + e^-1.5); m = -0.5 for ≥ 1.1.
    [above] = score(rubric(efficient(0.9, margin=0.2)), straight_clean_grasp()).criteria
    [below] = score(rubric(efficient(1.1, margin=0.2)), straight_clean_grasp()).criteria
    [far] = score(rubric(efficient(0.5, margin=0.2)), straight_clean_grasp()).criteria

    assert above.p_pass == pytest.approx(0.8176, abs=1e-4)
    assert below.p_pass == pytest.approx(0.1824, abs=1e-4)
    assert (far.status, far.p_pass) == ("pass", pytest.approx(0.99945, abs=1e-5))


def test_needs_review_episodes_at_different_margins_get_different_confidences():
    nearer = score(rubric(efficient(0.95, margin=0.2)), straight_clean_grasp())
    farther = score(rubric(efficient(0.9, margin=0.2)), straight_clean_grasp())

    assert nearer.decision == farther.decision == "needs_review"
    assert nearer.confidence == pytest.approx(0.6792, abs=1e-4)  # m = 0.25
    assert farther.confidence == pytest.approx(0.8176, abs=1e-4)  # m = 0.5


def test_phrase_p_is_its_least_sure_criterion_and_p_keep_its_least_sure_hard_phrase():
    triage = score(
        rubric(
            first_try(),
            efficient(0.9, margin=0.2),
            efficient(0.95, margin=0.2),
            still(margin=0.0, hard=False),
        ),
        straight_clean_grasp(),
    )

    first, places, pauses = triage.phrases
    assert first.p_pass == 1.0  # a crisp count
    assert places.p_pass == pytest.approx(0.6792, abs=1e-4)
    assert pauses.hard is False
    assert triage.p_keep == pytest.approx(0.6792, abs=1e-4)
    assert triage.confidence == pytest.approx(0.6792, abs=1e-4)


def test_confidence_is_high_for_a_crisp_reject_and_a_crisp_keep():
    rejected = score(rubric(first_try()), facts(REGRASP_GRIPPER))
    kept = score(rubric(first_try(), efficient(0.5, margin=0.2)), straight_clean_grasp())

    assert (rejected.decision, rejected.p_keep, rejected.confidence) == ("reject", 0.0, 1.0)
    assert kept.decision == "keep"
    assert kept.confidence == pytest.approx(0.99945, abs=1e-5)


def test_no_value_gives_one_half():
    holds_to_the_end = facts(frames((0, 15), (1, 30)), CLEAN_Z)

    triage = score(rubric(still(window=Window(kind="after_release"))), holds_to_the_end)

    assert triage.criteria[0].p_pass == 0.5
    assert triage.confidence == 0.5


def test_an_inconclusive_fail_is_clamped_to_one_half_at_least():
    released_high = facts(CLEAN_GRIPPER, frames((DOWN, 18), (0.3, 27)))

    triage = score(rubric(release()), released_high)

    assert (triage.criteria[0].status, triage.criteria[0].p_pass) == ("fail", 0.5)
    assert triage.phrases[1].status == "unsure"


def test_a_conclusive_fail_beside_an_unconfirmed_one_rejects():
    # Released 30 cm up: an unconfirmed fail. Along a straight path it needs review; along a
    # path that doubles back, path efficiency fails it conclusively.
    released_high = facts(CLEAN_GRIPPER, frames((DOWN, 18), (0.3, 27)), STRAIGHT)
    wasteful = facts(
        CLEAN_GRIPPER,
        frames((DOWN, 18), (0.3, 27)),
        np.concatenate([np.linspace(0, 0.3, 30), np.linspace(0.3, 0.0, 15)]).tolist(),
    )

    assert score(rubric(release(), efficient(0.5)), released_high).decision == "needs_review"
    assert score(rubric(release(), efficient(0.5)), wasteful).decision == "reject"


def test_a_label_gives_its_phrase_p_one_or_zero():
    near = rubric(efficient(0.9, margin=0.2))

    passed = score(
        near, straight_clean_grasp(), [Label(phrase=PLACES, value="pass", source="review")]
    )
    failed = score(
        near, straight_clean_grasp(), [Label(phrase=PLACES, value="fail", source="review")]
    )

    assert (passed.phrases[1].p_pass, passed.confidence) == (1.0, 1.0)
    assert (failed.phrases[1].p_pass, failed.p_keep) == (0.0, 0.0)


# droid_1.0.1:1's shape: one closure (frames 15-29) that lifts 1.6 cm against the 2 cm rule.
SMALL_LIFT_Z = frames((DOWN, 20), (0.016, 25))


def test_a_closure_near_the_grasp_rule_makes_grasp_attempts_unsure_not_a_reject():
    triage = score(rubric(first_try()), facts(CLEAN_GRIPPER, SMALL_LIFT_Z))

    [result] = triage.criteria
    assert (result.status, result.uncertainty) == ("unsure", "near threshold (count)")
    assert result.measurement == "no grasp"
    evidence = "".join(s.text for s in result.evidence)
    assert evidence.endswith(
        "Unsure: the closure at 1.0 s rose 1.6 cm, within 1 cm of the 2 cm grasp rule."
    )
    # Read as no grasp it fails: 0.4 cm from the rule is 0.4 margins on the failing side.
    assert result.p_pass == pytest.approx(1 / (1 + np.exp(1.2)), abs=1e-4)
    assert triage.decision == "needs_review"
    assert text(triage).startswith(f'Needs review: "{FIRST_TRY}": near threshold (count)')


def test_a_closure_near_the_closed_level_makes_grasp_attempts_unsure():
    # A half closure to 0.25 before the grasp: a failed attempt at the 0.2 level, none at 0.3.
    gripper = frames((0, 5), (0.25, 5), (0, 5), (1, 15), (0, 15))
    z = frames((DOWN, 20), (UP, 25))

    [result] = score(rubric(first_try()), facts(gripper, z)).criteria

    assert (result.status, result.uncertainty) == ("unsure", "near threshold (count)")
    assert "closed to 0.25, within 0.1 of the 0.2 level" in "".join(s.text for s in result.evidence)


def test_a_near_closure_that_cant_change_the_result_leaves_it_crisp():
    # Episode 42: three closures before the grasp, the middle one lifting 2.7 cm. Whether or not
    # it counts as lifting, the grasp is the last one and there were failed attempts.
    gripper = frames((0, 5), (1, 5), (0, 5), (1, 5), (0, 5), (1, 5), (0, 5), (1, 10))
    z = frames((DOWN, 17), (0.027, 13), (DOWN, 7), (UP, 8))

    triage = score(rubric(first_try()), facts(gripper, z))

    assert (triage.criteria[0].status, triage.criteria[0].uncertainty) == ("fail", None)
    assert triage.decision == "reject"


def test_a_missing_source_or_failed_step_makes_its_criteria_unsure():
    data = straight_clean_grasp()
    failed = EpisodeFacts(data.signals, unavailable={"robot data": "step failed"})
    missing = EpisodeFacts(data.signals, unavailable={"robot data": "source missing"})

    [step] = score(rubric(efficient(0.5)), failed).criteria
    [source] = score(rubric(efficient(0.5)), missing).criteria

    assert (step.status, step.uncertainty, step.value, step.p_pass) == (
        "unsure",
        "step failed",
        None,
        0.5,
    )
    assert source.uncertainty == "source missing"
