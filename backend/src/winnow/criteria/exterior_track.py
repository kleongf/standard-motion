"""Tracked primitives from the exterior object track, seeded from the hand-drawn box: whether the
object fell after release, and how far it moved. Placement against the target box is in
`criteria.placement`.

Without a hand-drawn box there is no exterior track, so these are unsure ("source missing") and
the Episode goes to Needs review rather than being guessed at.
"""

import math

from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.grasps import Grasps, Interval
from winnow.criteria.measured import Measurement, at_times
from winnow.criteria.models import Criterion, Moment, TextSpan
from winnow.criteria.track_frames import Stretch, centre, no_track, robot_frame

FALL_WINDOW_S = 1.0  # a fall shows within this long of the release
MIN_SIDE_PX = 1.0  # what a degenerate SAM box's side counts as, so nothing divides by zero


def no_exterior_track() -> Measurement:
    return no_track("exterior", "box the object on Prepare to track it.")


def _fall(drops: dict[int, float], stretch: Stretch, released_s: float) -> Measurement:
    lowest = max(drops, key=lambda f: drops[f])
    fell = round(max(0.0, drops[lowest]), 3)
    moments = [Moment(t=released_s, label="Release")]
    after = f"in the {FALL_WINDOW_S:g} s after release at "
    if fell == 0:
        evidence = [TextSpan(text=f"Stayed put {after}"), *at_times([released_s])]
        return Measurement(fell, "0.0 box-heights", [*evidence, TextSpan(text=".")], moments)
    lowest_s = stretch.time(lowest)
    evidence = [
        TextSpan(text=f"Fell {fell:.1f} box-heights {after}"),
        *at_times([released_s]),
        TextSpan(text=", lowest at "),
        *at_times([lowest_s]),
        TextSpan(text="."),
    ]
    moments.append(Moment(t=lowest_s, label="Lowest"))
    return Measurement(fell, f"{fell:.1f} box-heights", evidence, moments, lowest_s)


def fall_after_release(
    criterion: Criterion, facts: EpisodeFacts, grasps: Grasps, window: Interval
) -> Measurement:
    """How far the object's box drops in the second after the grasp opens, in the box-heights it
    had at release: set by the release, not the window, like `release_height_m`. A leap straight
    down is the fall itself, so it never counts as SAM losing the object."""
    track = facts.exterior
    if track is None:
        return no_exterior_track()
    grasp = grasps.the_grasp
    if grasp is None or not grasps.released:
        why = "No grasp to release." if grasp is None else "No release: the grasp never opened."
        evidence = [TextSpan(text=why)]
        return Measurement(
            None, "no release", evidence, [], status="unsure", uncertainty="window empty"
        )
    released_s = facts.t[grasp.end + 1]
    end = robot_frame(facts, released_s + FALL_WINDOW_S)
    stretch = Stretch.read(track, facts, grasp.end + 1, end)
    seen = stretch.seen
    if not seen:
        return stretch.no_box("after release")
    ref = stretch.boxes[seen[0]]
    height = max(ref.bottom - ref.top, MIN_SIDE_PX)
    drops = {f: round((centre(stretch.boxes[f])[1] - centre(ref)[1]) / height, 3) for f in seen}
    plot = stretch.plot("Drop since release", "box-heights", criterion.threshold, drops)
    return stretch.judged(_fall(drops, stretch, released_s), plot, falls_ok=True)


def object_displacement(
    criterion: Criterion, facts: EpisodeFacts, grasps: Grasps, window: Interval
) -> Measurement:
    """How far the object's box centre moved from its first box in the window to its last, in the
    first box's widths."""
    track = facts.exterior
    if track is None:
        return no_exterior_track()
    stretch = Stretch.read(track, facts, window.start, window.end)
    seen = stretch.seen
    if not seen:
        return stretch.no_box("in this window")
    first = centre(stretch.boxes[seen[0]])
    box = stretch.boxes[seen[0]]
    width = max(box.right - box.left, MIN_SIDE_PX)
    moved = {f: round(math.dist(centre(stretch.boxes[f]), first) / width, 3) for f in seen}
    start_s, end_s = stretch.time(seen[0]), stretch.time(seen[-1])
    value = moved[seen[-1]]
    evidence = [
        TextSpan(text=f"Moved {value:.1f} box-widths, from "),
        *at_times([start_s]),
        TextSpan(text=" to "),
        *at_times([end_s]),
        TextSpan(text="."),
    ]
    plot = stretch.plot("Distance from its first box", "box-widths", criterion.threshold, moved)
    moments = [Moment(t=start_s, label="From"), Moment(t=end_s, label="To")]
    measured = Measurement(value, f"{value:.1f} box-widths", evidence, moments, end_s)
    return stretch.judged(measured, plot)
