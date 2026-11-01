"""The Criteria catalog: per primitive, how to measure it and how to say it in English.

The metadata (kind, unit, params, conclusive, noise floor, source) lives in
`criteria.primitives`.
"""

from collections.abc import Callable
from dataclasses import dataclass

from winnow.criteria.exterior_track import fall_after_release, object_displacement
from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.grasps import Grasps, Interval
from winnow.criteria.in_hand import in_hand_lost_s
from winnow.criteria.measured import Measurement, grasp_attempts, release_height_m
from winnow.criteria.models import Criterion
from winnow.criteria.motion import active_duration_s, longest_still_s, path_efficiency
from winnow.criteria.placement import final_overlap
from winnow.criteria.primitives import Primitive
from winnow.visual.measure import ask_video

Measure = Callable[[Criterion, EpisodeFacts, Grasps, Interval], Measurement]


@dataclass(frozen=True)
class Entry:
    measure: Measure
    # The measured quantity in English; formatted with the Criterion's params.
    english: str


CATALOG: dict[Primitive, Entry] = {
    "grasp_attempts": Entry(grasp_attempts, "Grasp attempts, up to and including the grasp,"),
    "longest_still_s": Entry(
        longest_still_s, "Longest stretch with the arm under {speed_below_m_s:g} m/s"
    ),
    "release_height_m": Entry(
        release_height_m, "Release height above where the object was picked up"
    ),
    "active_duration_s": Entry(active_duration_s, "Time the arm is moving"),
    "path_efficiency": Entry(path_efficiency, "Path efficiency (straight line over path)"),
    "in_hand_lost_s": Entry(
        in_hand_lost_s, "Time the object is out of the closed gripper (wrist view)"
    ),
    "fall_after_release": Entry(
        fall_after_release, "How far the object falls within 1 s of release"
    ),
    "final_overlap": Entry(final_overlap, "Share of the object's final box inside the target box"),
    "object_displacement": Entry(object_displacement, "How far the object moved, start to end,"),
    # A visual Criterion reads as its question (`criteria.english`), not a comparison.
    "ask_video": Entry(ask_video, "Spark's samples answering pass"),
}
