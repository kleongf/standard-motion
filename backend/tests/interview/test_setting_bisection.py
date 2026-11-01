"""Grasp-setting questions on hand-built signals: which moment of an Episode each setting asks
about, and bisecting a setting over the anchor pool's moments. The fixture gripper only ever
reads 0 or 1, so its closures can't show a level between."""

import numpy as np

from winnow.episodes.models import EpisodeSignals
from winnow.interview.anchor import AnchorResult, setting_points
from winnow.interview.models import Clip, SettingName, StoredAnswer
from winnow.interview.settings_answers import answer_setting
from winnow.interview.settings_questions import setting_questions
from winnow.rubric.models import RubricDraft
from winnow.rubric.seed import SEEDED_SETTINGS

FPS = 10.0


def signals(gripper: list[float], z: list[float]) -> EpisodeSignals:
    n = len(gripper)
    position = np.zeros((n, 3))
    position[:, 2] = z
    return EpisodeSignals(
        episode_index=0,
        fps=FPS,
        timestamps=np.arange(n) / FPS + 100.0,  # stamps needn't start at 0
        position=position,
        gripper=np.array(gripper, dtype=np.float64),
        dataset_outcome=None,
    )


def test_each_setting_asks_about_the_closure_nearest_it():
    # Frames 10-19 close to 0.25 and rise 1.5 cm; frames 40-59 close to 0.9 and rise 10 cm.
    gripper = [0.0] * 80
    gripper[10:20] = [0.25] * 10
    gripper[40:60] = [0.9] * 20
    z = [0.0] * 80
    z[10:20] = list(np.linspace(0.0, 0.015, 10))
    z[40:60] = list(np.linspace(0.0, 0.10, 20))
    z[60:] = [0.10] * 20

    points = setting_points(
        "droid_100:7",
        ["exterior_image_1_left", "wrist_image_left"],
        signals(gripper, z),
        SEEDED_SETTINGS,  # closed above 0.2 ± 0.1; the grasp rises 2 cm ± 1 cm
    )

    level, rise = points["gripper_closed_level"], points["grasp_rise_m"]
    assert (level.value, level.measurement, level.camera) == (
        0.25,
        "closed to 0.25",
        "wrist_image_left",  # the fingers show there
    )
    assert level.clip == Clip(start=0.0, end=2.0)  # its peak, at 1 s, ± 1 s
    assert (round(rise.value, 4), rise.measurement, rise.camera) == (
        0.015,
        "rose 1.5 cm",
        "exterior_image_1_left",
    )
    assert rise.clip == Clip(start=0.0, end=2.9)  # from its closing to its top, ± 1 s


def test_an_episode_whose_gripper_never_closes_has_no_moment():
    points = setting_points(
        "droid_100:4", ["wrist_image_left"], signals([0.0] * 20, [0.0] * 20), SEEDED_SETTINGS
    )

    assert points == {}


def moment(episode: int, peak: float) -> AnchorResult:
    return AnchorResult(
        f"droid_100:{episode}", peak, f"closed to {peak:.2f}", None, Clip(start=0, end=1)
    )


def test_bisecting_the_closed_level_takes_at_most_three_questions_and_clears_its_assumption():
    peaks = [0.15, 0.3, 0.45, 0.6, 0.75, 0.9]
    moments: dict[SettingName, list[AnchorResult]] = {
        "gripper_closed_level": [moment(i, p) for i, p in enumerate(peaks)]
    }
    draft = RubricDraft(
        description="", phrases=[], settings=SEEDED_SETTINGS, criteria=[], compiled_at="now"
    )
    answers: list[StoredAnswer] = []

    asked: list[float] = []
    while questions := setting_questions(draft, moments, answers):
        question = questions[0]
        assert question.setting == "gripper_closed_level"
        asked.append(question.value)
        closed = "pass" if question.value > 0.5 else "fail"  # the curator sees it closed past 0.5
        stored, changed = answer_setting(
            draft, answers, moments["gripper_closed_level"], question, closed
        )
        answers.append(stored)
        draft = changed or draft

    assert len(asked) <= 3
    assert asked[0] == 0.15  # nearest the assumed 0.2 first
    level = draft.settings.gripper_closed_level
    assert (level.value, level.margin, level.assumption) == (0.525, 0.15, None)
    assert answers[-1].resolution == "set"
    assert answers[-1].effect.endswith("Gripper closed level 0.2 → 0.525, margin ± 0.15.")


def rise(episode: int, metres: float) -> AnchorResult:
    return AnchorResult(
        f"droid_100:{episode}", metres, f"rose {metres * 100:.1f} cm", None, Clip(start=0, end=1)
    )


def test_bisecting_the_grasp_rise_stops_at_three_questions_with_moments_still_left():
    rises = [0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.06, 0.08]
    moments: dict[SettingName, list[AnchorResult]] = {
        "grasp_rise_m": [rise(i, r) for i, r in enumerate(rises)]
    }
    draft = RubricDraft(
        description="", phrases=[], settings=SEEDED_SETTINGS, criteria=[], compiled_at="now"
    )
    answers: list[StoredAnswer] = []

    asked: list[float] = []
    while questions := setting_questions(draft, moments, answers):
        question = questions[0]
        assert question.setting == "grasp_rise_m"
        assert (question.asked, question.max_questions) == (len(asked), 3)
        asked.append(question.value)
        lifted = "pass" if question.value >= 0.035 else "fail"  # a lift is 3.5 cm or more
        stored, changed = answer_setting(draft, answers, moments["grasp_rise_m"], question, lifted)
        answers.append(stored)
        draft = changed or draft

    # 2 cm (nearest the assumed 2 cm), then the middle of the rest above it, then of those
    # between: 4 cm is still inside the bracket, but the third answer settles it.
    assert asked == [0.02, 0.05, 0.03]
    rule = draft.settings.grasp_rise_m
    assert (rule.value, rule.margin, rule.assumption) == (0.04, 0.02, None)
    assert answers[-1].resolution == "set"
    assert [a.resolution for a in answers[:-1]] == [None, None]
