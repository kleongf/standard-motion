"""Each measured primitive on synthetic robot data, through the scoring function."""

import numpy as np
import pytest

from tests.triage.robot_data import (
    CLEAN_GRIPPER,
    PLACES,
    facts,
    frames,
    release,
    rubric,
    text,
)
from winnow.criteria.models import Criterion, Window
from winnow.triage.scoring import score

# Grasped at frame 15 at the object's height (0 m), carried up, released at frame 30.
CARRY_Z = frames((0.0, 18), (0.10, 27))


def test_release_height_is_how_far_above_its_pick_up_height_the_grasp_opened():
    lowered = frames((0.0, 18), (0.10, 8), (0.02, 19))

    [high] = score(rubric(release()), facts(CLEAN_GRIPPER, CARRY_Z)).criteria
    [low] = score(rubric(release()), facts(CLEAN_GRIPPER, lowered)).criteria

    assert (high.value, high.measurement) == (pytest.approx(0.10), "10 cm")
    assert (low.value, low.status) == (pytest.approx(0.02), "pass")
    assert [(m.label, m.t) for m in high.moments] == [("Release", 2.0)]
    assert high.at_s == 2.0


def test_a_high_release_is_an_unconfirmed_fail_so_the_episode_needs_review_not_reject():
    # Stacking: placing on top of something is a high release, so release height alone can't
    # reject.
    triage = score(rubric(release()), facts(CLEAN_GRIPPER, CARRY_Z))

    [result] = triage.criteria
    assert (result.status, result.uncertainty) == ("fail", "unconfirmed fail")
    assert triage.phrases[1].status == "unsure"
    assert triage.decision == "needs_review"
    assert text(triage).startswith(f'Needs review: "{PLACES}": unconfirmed fail')


def test_a_grasp_held_to_the_end_has_no_release_height():
    held = frames((0, 15), (1, 30))

    triage = score(rubric(release()), facts(held, CARRY_Z))

    [result] = triage.criteria
    assert (result.status, result.value, result.uncertainty) == ("unsure", None, "window empty")
    assert text(triage) == f'Needs review: "{PLACES}": window empty (no release).'


def active(threshold: float = 2.0) -> Criterion:
    return Criterion(
        id="active",
        phrase=PLACES,
        primitive="active_duration_s",
        comparator="<=",
        threshold=threshold,
        unit="s",
    )


def test_active_duration_runs_from_when_the_arm_first_moves_to_when_it_last_stops():
    # Still for 1 s, moves 30 cm over 2 s, still for 1 s.
    x = np.concatenate([np.zeros(15), np.linspace(0, 0.3, 30), np.full(15, 0.3)])

    [result] = score(rubric(active()), facts([0.0] * 60, x=x.tolist())).criteria

    assert result.value == pytest.approx(2.0, abs=0.2)
    assert [m.label for m in result.moments] == ["Starts", "Stops"]


def efficient(window: Window | None = None) -> Criterion:
    return Criterion(
        id="path",
        phrase=PLACES,
        primitive="path_efficiency",
        comparator=">=",
        threshold=0.7,
        unit="ratio",
        window=window or Window(),
    )


def test_path_efficiency_is_the_straight_line_over_the_path_travelled():
    straight = np.linspace(0, 0.3, 45)
    there_and_halfway_back = np.concatenate([np.linspace(0, 0.3, 30), np.linspace(0.3, 0.15, 15)])

    [direct] = score(rubric(efficient()), facts([0.0] * 45, x=straight.tolist())).criteria
    [wasteful] = score(
        rubric(efficient()), facts([0.0] * 45, x=there_and_halfway_back.tolist())
    ).criteria

    assert (direct.value, direct.status) == (pytest.approx(1.0), "pass")
    assert (wasteful.value, wasteful.status) == (pytest.approx(0.15 / 0.45, abs=0.01), "fail")


def test_path_efficiency_reads_only_its_window():
    # Wasteful before the grasp (frames 0-14), then a straight carry up and across.
    x = np.concatenate([np.linspace(0, 0.3, 10), np.linspace(0.3, 0.0, 5), np.linspace(0, 0.3, 30)])
    z = np.concatenate([np.zeros(15), np.linspace(0, 0.1, 30)])

    [holding] = score(
        rubric(efficient(Window(kind="holding"))), facts(CLEAN_GRIPPER, z.tolist(), x.tolist())
    ).criteria
    [whole] = score(rubric(efficient()), facts(CLEAN_GRIPPER, z.tolist(), x.tolist())).criteria

    assert (holding.value, whole.status) == (pytest.approx(1.0), "fail")
