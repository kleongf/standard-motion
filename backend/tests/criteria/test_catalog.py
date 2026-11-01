import numpy as np
import pytest
from pydantic import ValidationError

from winnow.criteria.english import english
from winnow.criteria.grasps import closures
from winnow.criteria.models import Criterion, Window
from winnow.rubric.seed import SEEDED


def test_closures_are_the_stretches_above_the_closed_level():
    gripper = np.asarray([0, 0.3, 0, 0.5, 0.16, 0.5, 0.6, 0.6, 0])

    assert [(c.start, c.end) for c in closures(gripper, 0.2)] == [(1, 1), (3, 3), (5, 7)]
    assert [(c.start, c.end) for c in closures(gripper, 0.1)] == [(1, 1), (3, 7)]


def test_the_english_is_rendered_from_the_fields():
    attempts = Criterion(
        id="a",
        phrase="p",
        primitive="grasp_attempts",
        comparator="<=",
        threshold=1,
        unit="attempts",
    )
    still = Criterion(
        id="b",
        phrase="p",
        primitive="longest_still_s",
        params={"speed_below_m_s": 0.01},
        comparator="<",
        threshold=1.5,
        unit="s",
        window=Window(kind="holding"),
    )

    assert english(attempts) == "Grasp attempts, up to and including the grasp, ≤ 1"
    assert english(still) == "Longest stretch with the arm under 0.01 m/s, while holding, < 1.5 s"
    assert attempts.kind == still.kind == "measured"


def test_the_seeded_tracked_criteria_read_as_english():
    by_id = {c.id: c for c in SEEDED.criteria}

    assert english(by_id["in-hand-lost"]) == (
        "Time the object is out of the closed gripper (wrist view), while holding, < 0.4 s"
    )
    assert english(by_id["fall-after-release"]) == (
        "How far the object falls within 1 s of release ≤ 0.5 box-heights"
    )
    assert english(by_id["final-overlap"]) == (
        "Share of the object's final box inside the target box, last 1 s, ≥ 0.50"
    )
    assert by_id["in-hand-lost"].kind == by_id["final-overlap"].kind == "tracked"


def test_params_must_match_the_primitive_and_last_n_s_needs_its_seconds():
    with pytest.raises(ValidationError, match="speed_below_m_s"):
        Criterion(
            id="b", phrase="p", primitive="longest_still_s", comparator="<", threshold=1, unit="s"
        )
    with pytest.raises(ValidationError, match="seconds"):
        Window(kind="last_n_s")
    assert Window(kind="last_n_s", seconds=2).seconds == 2
