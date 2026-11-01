"""Measured primitives about the arm's motion in a Criterion's window, from robot data alone."""

import numpy as np

from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.grasps import Grasps, Interval
from winnow.criteria.measured import Measurement, at_times, seconds
from winnow.criteria.models import Criterion, Moment, TextSpan
from winnow.episodes.models import FloatArray

MOVING_SPEED_M_S = 0.01  # slower than this, the arm counts as stopped
MIN_PATH_M = 0.01  # a shorter path is too small to call wasteful


def _longest_run(still: np.ndarray) -> tuple[int, int]:
    """(start, length) of the longest run of True."""
    best = (0, 0)
    start = 0
    for i, is_still in enumerate([*still.tolist(), False]):
        if not is_still:
            if i - start > best[1]:
                best = (start, i - start)
            start = i + 1
    return best


def longest_still_s(
    criterion: Criterion, facts: EpisodeFacts, grasps: Grasps, window: Interval
) -> Measurement:
    """The longest stretch in the window, after the arm first moves and before it last stops,
    where the end effector is slower than `speed_below_m_s`."""
    below = criterion.params["speed_below_m_s"]
    speed = facts.speed[window.start : window.end + 1]
    moving = np.flatnonzero(speed >= below)
    if len(moving) == 0:
        return Measurement(0.0, "0.0 s", [TextSpan(text="The arm never moved here.")], [])
    first = window.start + int(moving[0])
    start, length = _longest_run(speed[moving[0] : moving[-1] + 1] < below)
    still_s = length / facts.signals.fps
    if length == 0:
        return Measurement(0.0, "0.0 s", [TextSpan(text="The arm never stopped.")], [])
    t0 = facts.t[first + start]
    t1 = facts.t[min(first + start + length, len(facts.t) - 1)]
    evidence = [
        TextSpan(text=f"Still (under {below:g} m/s) for {seconds(still_s)}, from "),
        *at_times([t0]),
        TextSpan(text=" to "),
        *at_times([t1]),
        TextSpan(text="."),
    ]
    moments = [Moment(t=t0, label="Stops"), Moment(t=t1, label="Moves again")]
    return Measurement(round(still_s, 3), seconds(still_s), evidence, moments, t0)


def active_duration_s(
    criterion: Criterion, facts: EpisodeFacts, grasps: Grasps, window: Interval
) -> Measurement:
    """From when the arm first moves in the window to when it last stops."""
    speed = facts.speed[window.start : window.end + 1]
    moving = np.flatnonzero(speed >= MOVING_SPEED_M_S)
    if len(moving) == 0:
        return Measurement(0.0, "0.0 s", [TextSpan(text="The arm never moved here.")], [])
    t0 = facts.t[window.start + int(moving[0])]
    t1 = facts.t[window.start + int(moving[-1])]
    active = round(t1 - t0, 3)
    evidence = [
        TextSpan(text=f"Active for {seconds(active)}, from "),
        *at_times([t0]),
        TextSpan(text=" to "),
        *at_times([t1]),
        TextSpan(text="."),
    ]
    over = t0 + criterion.threshold  # where a too-long Episode runs past the threshold
    at_s = over if t0 <= over <= t1 else t1
    moments = [Moment(t=t0, label="Starts"), Moment(t=t1, label="Stops")]
    return Measurement(active, seconds(active), evidence, moments, at_s)


def path_efficiency(
    criterion: Criterion, facts: EpisodeFacts, grasps: Grasps, window: Interval
) -> Measurement:
    """The straight line from the window's first end-effector position to its last, over the
    path the end effector travelled between them: 1 is direct."""
    position = facts.signals.position[window.start : window.end + 1]
    steps: FloatArray = np.linalg.norm(np.diff(position, axis=0), axis=1)
    path = float(np.sum(steps))
    t0, t1 = facts.t[window.start], facts.t[window.end]
    moments = [Moment(t=t0, label="From"), Moment(t=t1, label="To")]
    if path < MIN_PATH_M:
        evidence = [TextSpan(text="The arm barely moved here, so it wasted no motion.")]
        return Measurement(1.0, "1.00", evidence, moments)
    line: FloatArray = position[-1] - position[0]
    straight = float(np.sqrt(np.sum(line**2)))
    ratio = straight / path
    evidence = [
        TextSpan(text=f"Travelled {path * 100:.0f} cm to get {straight * 100:.0f} cm, from "),
        *at_times([t0]),
        TextSpan(text=" to "),
        *at_times([t1]),
        TextSpan(text="."),
    ]
    return Measurement(round(ratio, 3), f"{ratio:.2f}", evidence, moments, t0)
