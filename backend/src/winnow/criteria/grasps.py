"""The grasp rule: which gripper closure is the grasp, and which were failed attempts.

The grasp is the last closure during which the end effector rises at least the Rubric's
`grasp_rise_m`; earlier closures are failed attempts. Closures are read against the Rubric's
gripper-closed level, never a hard-coded one.
"""

from dataclasses import dataclass

import numpy as np

from winnow.criteria.models import RubricSettings
from winnow.episodes.models import EpisodeSignals, FloatArray


@dataclass(frozen=True)
class Interval:
    start: int  # first frame, inclusive
    end: int  # last frame, inclusive


def closures(gripper: FloatArray, level: float) -> list[Interval]:
    """Each stretch of frames where the gripper is closed (above `level`)."""
    closed = gripper > level
    intervals: list[Interval] = []
    start: int | None = None
    for i, is_closed in enumerate(closed):
        if is_closed and start is None:
            start = i
        elif not is_closed and start is not None:
            intervals.append(Interval(start, i - 1))
            start = None
    if start is not None:
        intervals.append(Interval(start, len(closed) - 1))
    return intervals


def rise_m(z: FloatArray, closure: Interval) -> float:
    """The most the end effector climbed during a closure, from its lowest point so far."""
    heights = z[closure.start : closure.end + 1]
    return float(np.max(heights - np.minimum.accumulate(heights)))


@dataclass(frozen=True)
class Grasps:
    closures: list[Interval]
    grasp: int | None  # index into `closures`; None when no closure rose enough
    frames: int  # in the Episode
    released: bool  # the grasp opened before the Episode ended
    settings: RubricSettings  # the gripper-closed level and grasp rule they were read with

    @property
    def rise_rule_m(self) -> float:
        """How far the arm had to rise for a closure to be the grasp."""
        return self.settings.grasp_rise_m.value

    @property
    def failed(self) -> list[Interval]:
        """Closures before the grasp; all of them when there is none."""
        return self.closures if self.grasp is None else self.closures[: self.grasp]

    @property
    def the_grasp(self) -> Interval | None:
        return None if self.grasp is None else self.closures[self.grasp]


def find_grasps(signals: EpisodeSignals, settings: RubricSettings) -> Grasps:
    found = closures(signals.gripper, settings.gripper_closed_level.value)
    z = signals.position[:, 2]
    lifting = [i for i, c in enumerate(found) if rise_m(z, c) >= settings.grasp_rise_m.value]
    grasp = lifting[-1] if lifting else None
    frames = len(signals.gripper)
    released = grasp is not None and found[grasp].end < frames - 1
    return Grasps(found, grasp, frames, released, settings)
