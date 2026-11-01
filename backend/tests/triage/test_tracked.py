"""Each tracked primitive on synthetic SAM tracks, through the scoring function."""

import pytest

from tests.triage.robot_data import CLEAN_GRIPPER, CLEAN_Z, facts
from tests.triage.tracks import (
    DROPS,
    FINGERS,
    FRAMES,
    PLACES,
    box_at,
    fall,
    held,
    in_hand,
    overlap,
    rubric,
    target,
    track,
    with_tracks,
)
from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.models import Criterion
from winnow.tracking.models import TrackBox
from winnow.triage.models import CriterionResult
from winnow.triage.scoring import score


def clean() -> EpisodeFacts:
    """One grasp, closed on 5 fps frames 5-9 (1.0-1.9 s), released at 2.0 s."""
    return facts(CLEAN_GRIPPER, CLEAN_Z)


def score_one(criterion: Criterion, episode: EpisodeFacts) -> list[CriterionResult]:
    return score(rubric(criterion), episode).criteria


def test_an_object_held_between_the_fingers_is_never_lost():
    [result] = score_one(in_hand(), with_tracks(clean(), wrist=held()))

    assert (result.kind, result.value, result.status) == ("tracked", 0.0, "pass")


def test_an_object_gone_from_the_fingers_while_closed_is_lost_for_that_long():
    # It slips at 1.2 s (frame 6) and is gone from the wrist view until the grasp opens.
    slipped = held(range(6))

    [result] = score_one(in_hand(), with_tracks(clean(), wrist=slipped))

    assert (result.value, result.status, result.uncertainty) == (pytest.approx(0.8), "fail", None)
    assert result.at_s == pytest.approx(1.2)


def test_the_object_leaving_the_fingers_as_the_gripper_opens_is_the_release_not_a_slip():
    # The gripper starts opening at 1.6 s (frame 24) but reads closed until 2.0 s; the wrist
    # view loses the object from 1.6 s (5 fps frames 8 and 9).
    opening = [*CLEAN_GRIPPER[:24], 0.9, 0.9, 0.9, 0.6, 0.6, 0.6, *CLEAN_GRIPPER[30:]]

    [result] = score_one(in_hand(), with_tracks(facts(opening, CLEAN_Z), wrist=held(range(8))))

    assert (result.value, result.status) == (0.0, "pass")


def test_an_object_far_from_the_fingers_is_out_of_hand_and_moving_away_is_no_lost_track():
    # From 1.2 s the box sits 70 px (1.75 box-widths) below the fingers: a leap of over a
    # box-width, but after the object left the hand, so it is the slip, not SAM losing it.
    dangling = [box_at(f, FINGERS if f < 6 else (190, 175)) for f in range(FRAMES)]

    [result] = score_one(in_hand(), with_tracks(clean(), wrist=track("wrist", dangling)))

    assert (result.value, result.status) == (pytest.approx(0.8), "fail")
    assert result.track_plot is not None
    assert [p.value for p in result.track_plot.points] == [0, 1.75, 1.75, 1.75, 1.75]


def test_a_track_lost_in_the_criterions_window_makes_it_unsure_but_not_one_lost_outside_it():
    swollen_in = [box_at(f, FINGERS, size=100 if f == 7 else 40) for f in range(FRAMES)]
    swollen_before = [box_at(f, FINGERS, size=100 if f == 2 else 40) for f in range(FRAMES)]

    [inside] = score_one(in_hand(), with_tracks(clean(), wrist=track("wrist", swollen_in)))
    [outside] = score_one(in_hand(), with_tracks(clean(), wrist=track("wrist", swollen_before)))

    assert (inside.status, inside.uncertainty, inside.p_pass) == ("unsure", "track lost", 0.5)
    assert "its box swelled at 1.4 s" in "".join(s.text for s in inside.evidence)
    assert (outside.status, outside.uncertainty) == ("pass", None)


SET_DOWN = (160.0, 100.0)  # where the exterior view sees the object once placed


def placed(at: tuple[float, float] = SET_DOWN, size: float = 30) -> list[TrackBox]:
    """An exterior track of an object resting at `at` throughout."""
    return [box_at(f, at, size) for f in range(FRAMES)]


def test_an_object_that_stays_put_after_release_has_not_fallen():
    [result] = score_one(fall(), with_tracks(clean(), exterior=track("exterior", placed())))

    assert (result.value, result.status) == (0.0, "pass")


def test_an_object_dropping_after_release_falls_that_many_box_heights():
    # Released at 2.0 s (frame 10); then it falls 30 px (one box-height) a frame for two frames.
    boxes = placed()
    boxes[11:] = [box_at(f, (160, 130 if f == 11 else 160), 30) for f in range(11, FRAMES)]

    [result] = score_one(fall(), with_tracks(clean(), exterior=track("exterior", boxes)))

    assert (result.value, result.status) == (pytest.approx(2.0), "fail")
    assert result.at_s == pytest.approx(2.4)
    assert result.track_plot is not None
    assert [p.value for p in result.track_plot.points] == [0, 1, 2, 2, 2]


AROUND = target(130, 70, 200, 130)  # around SET_DOWN's 30 px box
BESIDE = target(220, 70, 290, 130)


def test_final_overlap_is_the_share_of_the_final_box_inside_the_target_box():
    exterior = track("exterior", placed())
    # Its final box straddles the target's left edge at x = 160: half inside.
    straddling = target(160, 70, 230, 130)

    [inside] = score_one(overlap(), with_tracks(clean(), exterior=exterior, target_box=AROUND))
    [beside] = score_one(overlap(), with_tracks(clean(), exterior=exterior, target_box=BESIDE))
    [half] = score_one(overlap(), with_tracks(clean(), exterior=exterior, target_box=straddling))

    assert (inside.value, inside.status) == (1.0, "pass")
    assert (beside.value, beside.status, beside.at_s) == (0.0, "fail", 2.8)
    assert (half.value, half.status, half.uncertainty) == (0.5, "unsure", "near threshold")


def test_without_a_target_box_or_an_exterior_track_placement_is_unsure():
    exterior = track("exterior", placed())

    [no_target] = score_one(overlap(), with_tracks(clean(), exterior=exterior))
    [no_track] = score_one(overlap(), with_tracks(clean(), target_box=AROUND))

    assert (no_target.status, no_target.uncertainty) == ("unsure", "source missing")
    assert (no_track.status, no_track.uncertainty) == ("unsure", "source missing")
    assert no_target.p_pass == no_track.p_pass == 0.5


def test_placement_is_unsure_only_when_the_track_is_lost_in_its_last_second():
    early_jump = [box_at(f, (60, 100) if f < 3 else SET_DOWN, 30) for f in range(FRAMES)]
    late_jump = [box_at(f, (60, 100) if f < 13 else SET_DOWN, 30) for f in range(FRAMES)]

    [early] = score_one(
        overlap(), with_tracks(clean(), exterior=track("exterior", early_jump), target_box=AROUND)
    )
    [late] = score_one(
        overlap(), with_tracks(clean(), exterior=track("exterior", late_jump), target_box=AROUND)
    )

    assert (early.status, early.uncertainty) == ("pass", None)
    assert (late.status, late.uncertainty, late.value) == ("unsure", "track lost", 1.0)


def moved() -> Criterion:
    return Criterion(
        id="moved",
        phrase=PLACES,
        primitive="object_displacement",
        comparator=">=",
        threshold=1.0,
        unit="box-widths",
    )


def test_object_displacement_is_start_to_end_in_box_widths():
    # Carried 100 px right, 25 px a frame from 0.6 s: 3.3 of its 30 px box-widths.
    xs = [60 + 25 * min(max(f - 2, 0), 4) for f in range(FRAMES)]
    carried = track("exterior", [box_at(f, (x, 100), 30) for f, x in enumerate(xs)])

    [result] = score_one(moved(), with_tracks(clean(), exterior=carried))
    [unmoved] = score_one(moved(), with_tracks(clean(), exterior=track("exterior", placed())))

    assert (result.value, result.status) == (pytest.approx(3.333), "pass")
    assert result.track_plot is not None
    assert result.track_plot.points[-1].value == pytest.approx(3.333)
    assert (unmoved.value, unmoved.status) == (0.0, "fail")


def test_a_slip_in_transit_fails_in_hand_while_fall_after_release_passes_and_the_phrase_fails():
    # Gone from the fingers from 1.2 s; the exterior view sees it lying still after release.
    slipped = with_tracks(clean(), wrist=held(range(6)), exterior=track("exterior", placed()))
    # It was released 10 cm above where it was picked up: an inconclusive fail on its own.
    high_release = Criterion(
        id="release-height",
        phrase=DROPS,
        primitive="release_height_m",
        comparator="<=",
        threshold=0.05,
        unit="m",
    )

    triage = score(rubric(in_hand(), fall(), high_release), slipped)

    lost, fell, release = triage.criteria
    assert (lost.status, fell.status, release.status) == ("fail", "pass", "fail")
    assert triage.phrases[0].status == "fail"
    assert triage.decision == "reject"
    assert "".join(s.text for s in triage.reason).startswith(f'Rejected: "{DROPS}" failed. Gone')


def test_tracked_p_is_the_same_logistic_in_effective_margins_as_measured_p():
    # 1.0 inside against >= 0.95 with a 0.1 margin: m = 0.5, as in the measured test.
    near = overlap().model_copy(update={"threshold": 0.95, "margin": 0.1})
    exterior = track("exterior", placed())

    [result] = score_one(near, with_tracks(clean(), exterior=exterior, target_box=AROUND))

    assert (result.status, result.uncertainty) == ("unsure", "near threshold")
    assert result.p_pass == pytest.approx(0.8176, abs=1e-4)


def test_a_free_fall_is_a_fall_not_a_lost_track_but_a_sideways_leap_is():
    # Released at 2.0 s, the object drops 90 px (three box-heights) in one 5 fps frame: far over
    # a box-width, but straight down, as a fall goes. A leap sideways is SAM jumping elsewhere.
    dropped, leapt = placed(), placed()
    dropped[11:] = [box_at(f, (160, 190), 30) for f in range(11, FRAMES)]
    leapt[11:] = [box_at(f, (250, 100), 30) for f in range(11, FRAMES)]

    [fell] = score_one(fall(), with_tracks(clean(), exterior=track("exterior", dropped)))
    [jumped] = score_one(fall(), with_tracks(clean(), exterior=track("exterior", leapt)))

    assert (fell.value, fell.status, fell.uncertainty) == (pytest.approx(3.0), "fail", None)
    assert (jumped.status, jumped.uncertainty) == ("unsure", "track lost")


def test_with_no_wrist_track_in_hand_is_unsure():
    [result] = score_one(in_hand(), clean())

    assert (result.status, result.uncertainty, result.value) == ("unsure", "source missing", None)
