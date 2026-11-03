from standard_motion.tracking.health import track_health
from standard_motion.tracking.models import TrackBox


def box(frame: int, left: float = 100, top: float = 80, size: float = 40) -> TrackBox:
    return TrackBox(frame=frame, left=left, top=top, right=left + size, bottom=top + size)


def steady(frames: int) -> list[TrackBox]:
    """A 40 px box drifting 5 px right per frame: a held object, tracked well."""
    return [box(f, left=100 + 5 * f) for f in range(frames)]


def test_a_steady_track_is_healthy():
    health = track_health(steady(20), frames=20)

    assert (health.area_jumps, health.centre_jumps, health.missing_fraction) == ([], [], 0.0)
    assert not health.lost


def test_a_box_swelling_past_four_times_the_median_area_is_lost():
    boxes = steady(20)
    boxes[12] = box(12, left=60, top=40, size=90)  # 5x the area: bled over the arm

    health = track_health(boxes, frames=20)

    assert health.area_jumps == [12] and health.lost


def test_a_centre_jumping_over_one_box_width_is_lost():
    boxes = steady(20)
    boxes[8:] = [box(f, left=100 + 5 * f + 45) for f in range(8, 20)]  # leaps 50 px at frame 8

    health = track_health(boxes, frames=20)

    assert health.centre_jumps == [8] and health.lost


def test_no_box_on_over_a_fifth_of_frames_is_lost():
    assert track_health(steady(20)[:15], frames=20).lost  # 25% missing
    at_limit = track_health(steady(20)[:16], frames=20)  # exactly 20%: not over it
    assert at_limit.missing_fraction == 0.2 and not at_limit.lost


def test_a_window_judges_only_its_own_frames_against_the_whole_tracks_median():
    boxes = steady(20)[:10]  # nothing after frame 9
    boxes[3] = box(3, left=60, top=40, size=90)

    assert track_health(boxes, frames=20, window=range(5, 10)) == track_health(
        steady(10), frames=10, window=range(5, 10)
    )
    before = track_health(boxes, frames=20, window=range(0, 5))
    assert before.area_jumps == [3] and before.missing_fraction == 0.0
    assert track_health(boxes, frames=20, window=range(10, 20)).missing_fraction == 1.0
