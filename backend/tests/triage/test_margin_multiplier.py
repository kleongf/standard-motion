"""The margin multiplier s: effective margin = max(noise floor, interview gap) * s, 1 until
calibration tunes it."""

import numpy as np
import pytest

from tests.triage.robot_data import CLEAN_GRIPPER, PLACES, facts, rubric
from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.models import Criterion
from winnow.triage.confidence import effective_margin
from winnow.triage.scoring import score

STRAIGHT = np.linspace(0, 0.3, 45).tolist()
RISING = np.linspace(0, 0.1, 45).tolist()


def efficient(threshold: float, margin: float = 0.0) -> Criterion:
    return Criterion(
        id="path",
        phrase=PLACES,
        primitive="path_efficiency",
        comparator=">=",
        threshold=threshold,
        unit="ratio",
        margin=margin,
    )


def straight() -> EpisodeFacts:
    return facts(CLEAN_GRIPPER, RISING, STRAIGHT)  # path efficiency exactly 1


def test_the_effective_margin_scales_with_s_and_is_unchanged_at_1():
    criterion = efficient(0.9, margin=0.08)  # the noise floor, 0.05, is narrower

    assert effective_margin(criterion) == 0.08
    assert effective_margin(criterion, 1.0) == 0.08
    assert effective_margin(criterion, 2.0) == 0.16
    assert effective_margin(efficient(0.9), 0.5) == 0.025  # half the noise floor


def test_scoring_at_s_1_is_scoring_with_no_s():
    near = rubric(efficient(0.95, margin=0.08))

    assert score(near, straight(), s=1.0) == score(near, straight())


def test_a_wider_s_makes_a_crisp_result_unsure_and_moves_p():
    # 1.0 against ≥ 0.9 is 0.1 away: crisp outside a 0.08 margin, near threshold inside 0.16.
    criterion = efficient(0.9, margin=0.08)

    [crisp] = score(rubric(criterion), straight()).criteria
    [wide] = score(rubric(criterion), straight(), s=2.0).criteria

    assert (crisp.status, crisp.margin) == ("pass", 0.08)
    assert (wide.status, wide.uncertainty, wide.margin) == ("unsure", "near threshold", 0.16)
    # m = 0.1 / 0.16 = 0.625 -> p = 1/(1 + e^-1.875)
    assert wide.p_pass == pytest.approx(1 / (1 + np.exp(-1.875)), abs=1e-9)
