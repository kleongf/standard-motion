"""The pure scoring function: (Rubric, Episode facts, labels) -> Criterion results, Phrase
results, Triage decision and Reason."""

import numpy as np

from tests.triage.robot_data import (
    CLEAN_GRIPPER,
    CLEAN_Z,
    DOWN,
    FIRST_TRY,
    NO_PAUSES,
    REGRASP_GRIPPER,
    REGRASP_Z,
    UP,
    facts,
    first_try,
    frames,
    rubric,
    still,
    text,
)
from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.models import RubricSettings, Setting, Window
from winnow.episodes.models import EpisodeSignals
from winnow.triage.models import Label
from winnow.triage.scoring import score

CRISP = RubricSettings(
    gripper_closed_level=Setting(value=0.2, margin=0), grasp_rise_m=Setting(value=0.02, margin=0)
)


def test_one_closure_that_lifts_is_a_first_try_grasp_and_is_kept():
    triage = score(rubric(first_try()), facts(CLEAN_GRIPPER, CLEAN_Z))

    [result] = triage.criteria
    assert result.status == "pass"
    assert result.value == 1
    assert [m.label for m in result.moments] == ["Grasp"]
    assert result.moments[0].t == 1.0
    assert triage.decision == "keep"


def test_closures_before_the_grasp_are_failed_attempts_and_reject_with_their_times():
    triage = score(rubric(first_try()), facts(REGRASP_GRIPPER, REGRASP_Z))

    [result] = triage.criteria
    assert (result.status, result.value, result.measurement) == ("fail", 3, "3 attempts")
    assert [(m.label, round(m.t, 2)) for m in result.moments] == [
        ("Attempt 1", 0.67),
        ("Attempt 2", 1.33),
        ("Grasp", 2.0),
    ]
    assert triage.decision == "reject"
    assert text(triage) == (
        f'Rejected: "{FIRST_TRY}" failed. 2 failed grasp attempts, at 0.7 s and 1.3 s, '
        "before the grasp at 2.0 s."
    )
    assert [s.t for s in triage.reason if s.t is not None] == [
        result.moments[0].t,
        result.moments[1].t,
        result.moments[2].t,
    ]


def test_the_grasp_is_the_last_closure_that_rises_the_rubrics_grasp_rule():
    # The second closure (frames 15-24) lifts 1.5 cm: an attempt under a 2 cm rule, the grasp
    # under a 1 cm one. (No margins, so neither is unsure.)
    gripper = frames((0, 5), (1, 5), (0, 5), (1, 10), (0, 5))
    z = frames((DOWN, 18), (0.015, 12))
    lenient = CRISP.model_copy(update={"grasp_rise_m": Setting(value=0.01, margin=0)})

    strict = score(rubric(first_try(threshold=2), settings=CRISP), facts(gripper, z))
    loose = score(rubric(first_try(threshold=2), settings=lenient), facts(gripper, z))

    assert (strict.criteria[0].measurement, strict.decision) == ("no grasp", "reject")
    assert (loose.criteria[0].value, loose.decision) == (2, "keep")


def test_closed_means_above_the_rubrics_gripper_closed_level():
    # A half closure at 0.15 before the grasp: not a closure at the 0.2 level, one at 0.1.
    gripper = frames((0, 5), (0.15, 5), (0, 5), (1, 15), (0, 5))
    z = frames((DOWN, 20), (UP, 15))
    loose = CRISP.model_copy(update={"gripper_closed_level": Setting(value=0.1, margin=0)})

    assert score(rubric(first_try(), settings=CRISP), facts(gripper, z)).decision == "keep"
    assert score(rubric(first_try(), settings=loose), facts(gripper, z)).decision == "reject"


def test_no_grasp_fails_grasp_attempts_and_leaves_grasp_relative_windows_empty():
    never_closes = facts([0.0] * 45)
    holding = still(phrase=NO_PAUSES, window=Window(kind="holding"))
    after = still(phrase=NO_PAUSES, window=Window(kind="after_release"), id="after")
    before = still(phrase=NO_PAUSES, window=Window(kind="before_grasp"), id="before")

    triage = score(rubric(first_try(), holding, after, before), never_closes)

    attempts, *windowed = triage.criteria
    assert (attempts.status, attempts.measurement) == ("fail", "no grasp")
    assert "never closed" in "".join(s.text for s in attempts.evidence)
    for result in windowed:
        assert (result.status, result.uncertainty, result.window) == (
            "unsure",
            "window empty",
            None,
        )
    assert triage.decision == "reject"


def test_closures_that_never_lift_are_all_failed_attempts_with_no_grasp():
    triage = score(rubric(first_try(threshold=5)), facts(frames((0, 10), (1, 10), (0, 25))))

    [result] = triage.criteria
    assert (result.status, result.measurement) == ("fail", "no grasp")
    assert [m.label for m in result.moments] == ["Attempt 1"]
    assert text(triage).startswith(f'Rejected: "{FIRST_TRY}" failed. No grasp: 1 closure, at ')


def test_a_phrase_passes_only_when_all_its_criteria_pass():
    both = score(rubric(first_try(), still(phrase=FIRST_TRY)), facts(CLEAN_GRIPPER, CLEAN_Z))

    assert [p.status for p in both.phrases] == ["pass", None, None]
    assert both.decision == "keep"


def test_a_phrase_with_a_pass_and_an_unsure_is_unsure_and_needs_review():
    # The grasp never opens, so there is no after-release window.
    holds_to_the_end = facts(frames((0, 15), (1, 30)), frames((DOWN, 20), (UP, 25)))
    after = still(phrase=FIRST_TRY, window=Window(kind="after_release"))

    triage = score(rubric(first_try(), after), holds_to_the_end)

    assert [r.status for r in triage.criteria] == ["pass", "unsure"]
    assert triage.phrases[0].status == "unsure"
    assert triage.decision == "needs_review"
    assert text(triage) == f'Needs review: "{FIRST_TRY}": window empty (after release).'


def test_a_phrase_with_a_crisp_fail_fails_even_beside_an_unsure():
    regrasp_holding_on = facts(
        frames((0, 10), (1, 5), (0, 5), (1, 25)), frames((DOWN, 25), (UP, 20))
    )
    after = still(phrase=FIRST_TRY, window=Window(kind="after_release"))

    triage = score(rubric(first_try(), after), regrasp_holding_on)

    assert [r.status for r in triage.criteria] == ["fail", "unsure"]
    assert triage.phrases[0].status == "fail"
    assert triage.decision == "reject"


def test_weakest_link_any_failing_hard_phrase_rejects_over_an_unsure_one():
    holds = facts(frames((0, 5), (1, 5), (0, 5), (1, 30)), frames((DOWN, 20), (UP, 25)))
    unsure_pause = still(window=Window(kind="after_release"))

    triage = score(rubric(first_try(), unsure_pause), holds)

    assert [p.status for p in triage.phrases] == ["fail", None, "unsure"]
    assert triage.decision == "reject"


def test_soft_criteria_show_results_but_never_change_the_decision():
    soft = first_try(hard=False)

    triage = score(rubric(soft), facts(REGRASP_GRIPPER, REGRASP_Z))

    assert triage.criteria[0].status == "fail"
    assert triage.criteria[0].hard is False
    assert triage.phrases[0].hard is False
    assert triage.decision == "keep"


def test_the_reject_reason_starts_from_the_earliest_failure_and_lists_the_others():
    # The arm stops from frame 15 to 37; smoothed over 5 frames it is still from frame 17
    # (1.1 s). The grasp attempts fail earlier, at 0.7 s.
    data = facts(REGRASP_GRIPPER, REGRASP_Z)
    x = np.concatenate([np.linspace(0, 0.3, 15), np.full(22, 0.3), np.linspace(0.3, 0.6, 8)])
    position = data.signals.position.copy()
    position[:, 0] = x
    paused = EpisodeFacts(
        EpisodeSignals(0, 15.0, data.signals.timestamps, position, data.signals.gripper, True)
    )

    triage = score(rubric(still(threshold=0.5), first_try()), paused)

    assert [r.status for r in triage.criteria] == ["fail", "fail"]
    assert text(triage).startswith(f'Rejected: "{FIRST_TRY}" failed. 2 failed grasp attempts')
    assert text(triage).endswith(f'Also failed: "{NO_PAUSES}" at 1.1 s.')


def test_a_label_overrides_its_phrase_and_a_label_only_reject_names_it():
    label = Label(phrase=FIRST_TRY, value="fail", source="review")

    triage = score(rubric(first_try()), facts(CLEAN_GRIPPER, CLEAN_Z), [label])

    assert triage.criteria[0].status == "pass"
    assert triage.phrases[0].status == "fail" and triage.phrases[0].label == label
    assert triage.decision == "reject"
    assert text(triage) == f'Rejected: "{FIRST_TRY}" was marked fail in review.'


def test_a_pass_label_keeps_an_episode_its_criteria_rejected():
    label = Label(phrase=FIRST_TRY, value="pass", source="review")

    triage = score(rubric(first_try()), facts(REGRASP_GRIPPER, REGRASP_Z), [label])

    assert triage.decision == "keep"
