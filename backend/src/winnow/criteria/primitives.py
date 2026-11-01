"""Per-primitive catalog metadata: what each primitive measures and how far to trust it.

Adding a primitive means a name here, its metadata below, and a measure function and English
template in `criteria.catalog`.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

Primitive = Literal[
    "grasp_attempts",
    "longest_still_s",
    "release_height_m",
    "active_duration_s",
    "path_efficiency",
    "in_hand_lost_s",
    "fall_after_release",
    "final_overlap",
    "object_displacement",
    "ask_video",
]
Kind = Literal["measured", "tracked", "visual"]
# What a primitive reads; when a source is missing or its step failed, every Criterion reading it
# is unsure. `final_overlap` reads the target box as well as the exterior track, and is unsure
# without it.
Source = Literal["robot data", "wrist track", "exterior track", "video"]
# A visual Criterion asks its frozen question and this many paraphrases, one sample each.
PARAPHRASES = 2


@dataclass(frozen=True)
class PrimitiveInfo:
    kind: Kind
    unit: str
    # The names a Criterion's `params` must have, each with the value compile and the
    # capabilities manifest use when the Description doesn't say.
    params: Mapping[str, float]
    # A crisp fail of a conclusive primitive fails its Phrase on its own; an inconclusive one
    # (release_height_m, stacking) can only make it unsure.
    conclusive: bool
    # The smallest margin a measurement deserves, in `unit`. 0 for counts, which are unsure
    # through the Rubric settings' margins instead.
    noise_floor: float
    source: Source = "robot data"


PRIMITIVES: dict[Primitive, PrimitiveInfo] = {
    "grasp_attempts": PrimitiveInfo("measured", "attempts", {}, conclusive=True, noise_floor=0),
    "longest_still_s": PrimitiveInfo(
        "measured", "s", {"speed_below_m_s": 0.01}, conclusive=True, noise_floor=0.2
    ),
    "release_height_m": PrimitiveInfo("measured", "m", {}, conclusive=False, noise_floor=0.01),
    "active_duration_s": PrimitiveInfo("measured", "s", {}, conclusive=True, noise_floor=0.2),
    "path_efficiency": PrimitiveInfo("measured", "ratio", {}, conclusive=True, noise_floor=0.05),
    # Tracked: one 5 fps frame, or about what SAM's box jitters by at 320x180.
    "in_hand_lost_s": PrimitiveInfo(
        "tracked", "s", {}, conclusive=True, noise_floor=0.2, source="wrist track"
    ),
    "fall_after_release": PrimitiveInfo(
        "tracked", "box-heights", {}, conclusive=True, noise_floor=0.2, source="exterior track"
    ),
    "final_overlap": PrimitiveInfo(
        "tracked", "ratio", {}, conclusive=True, noise_floor=0.1, source="exterior track"
    ),
    "object_displacement": PrimitiveInfo(
        "tracked", "box-widths", {}, conclusive=True, noise_floor=0.25, source="exterior track"
    ),
    # Its value is how many samples answered pass; only a unanimous answer is conclusive.
    "ask_video": PrimitiveInfo(
        "visual", "samples", {}, conclusive=True, noise_floor=0, source="video"
    ),
}
