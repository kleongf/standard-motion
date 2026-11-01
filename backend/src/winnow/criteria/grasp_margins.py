"""How sure the grasp rule is: closures that sit within the margins of the Rubric's gripper-closed
level or grasp rule, and the grasps read at the edges of those margins.

A count can't be "near" its threshold the way a length can, so `grasp_attempts` is unsure
when reading the closures at the margins' edges would change its result (Episode 49's case:
a closure that rose 1.6 cm against a 2 cm rule).
"""

from dataclasses import dataclass
from itertools import product

import numpy as np

from winnow.criteria.grasps import Grasps, closures, find_grasps, rise_m
from winnow.criteria.models import RubricSettings, Setting
from winnow.episodes.models import EpisodeSignals


@dataclass(frozen=True)
class NearClosure:
    start: int  # first frame
    margins: float  # how far from the setting's value, in that setting's margins (0 to 1)
    why: str  # e.g. "rose 1.6 cm, within 1 cm of the 2 cm grasp rule"


def _edges(setting: Setting) -> tuple[float, ...]:
    if setting.margin == 0:
        return (setting.value,)
    return (setting.value - setting.margin, setting.value + setting.margin)


def readings(signals: EpisodeSignals, settings: RubricSettings) -> list[Grasps]:
    """The grasps read at each corner of the closed level's and the grasp rule's margins."""
    corners = product(_edges(settings.gripper_closed_level), _edges(settings.grasp_rise_m))
    return [
        find_grasps(
            signals,
            RubricSettings(
                gripper_closed_level=Setting(value=level, margin=0),
                grasp_rise_m=Setting(value=rise, margin=0),
            ),
        )
        for level, rise in corners
    ]


def _near_level(signals: EpisodeSignals, level: Setting) -> list[NearClosure]:
    if level.margin == 0:
        return []
    near: list[NearClosure] = []
    for closure in closures(signals.gripper, level.value - level.margin):
        peak = float(np.max(signals.gripper[closure.start : closure.end + 1]))
        if abs(peak - level.value) <= level.margin:
            why = f"closed to {peak:.2f}, within {level.margin:g} of the {level.value:g} level"
            near.append(NearClosure(closure.start, abs(peak - level.value) / level.margin, why))
    return near


def _near_rise(signals: EpisodeSignals, settings: RubricSettings) -> list[NearClosure]:
    rule = settings.grasp_rise_m
    if rule.margin == 0:
        return []
    near: list[NearClosure] = []
    z = signals.position[:, 2]
    for closure in closures(signals.gripper, settings.gripper_closed_level.value):
        rise = rise_m(z, closure)
        if abs(rise - rule.value) <= rule.margin:
            why = (
                f"rose {rise * 100:.1f} cm, within {rule.margin * 100:g} cm of the "
                f"{rule.value * 100:g} cm grasp rule"
            )
            near.append(NearClosure(closure.start, abs(rise - rule.value) / rule.margin, why))
    return near


def near_closures(signals: EpisodeSignals, settings: RubricSettings) -> list[NearClosure]:
    """Closures within the margins of the closed level or the grasp rule, nearest first."""
    near = _near_level(signals, settings.gripper_closed_level) + _near_rise(signals, settings)
    return sorted(near, key=lambda n: n.margins)
