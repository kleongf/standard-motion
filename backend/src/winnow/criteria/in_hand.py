"""`in_hand_lost_s`, from the wrist object track: how long the object is gone from the wrist view,
or far from the fingers, while the gripper is still closed and holding steady. A slip in transit.

The wrist camera is fixed to the gripper, so a held object stays where the wrist track was seeded:
between the fingertips. Its track's health is judged only while the object is in hand (up to the
last frame it is seen there), because after a slip, no box is the evidence, not SAM failing.
"""

import math
import statistics
from dataclasses import dataclass, replace

from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.grasps import Grasps, Interval
from winnow.criteria.measured import Measurement, at_times, seconds
from winnow.criteria.models import Criterion, Moment, TextSpan
from winnow.criteria.track_frames import Stretch, centre, median_width, no_track, robot_frame
from winnow.tracking.models import Track
from winnow.tracking.wrist import OBJECT_POINT, RECIPE_SIZE

FAR_WIDTHS = 1.5  # further than this from the fingers, in the track's box-widths, is out of hand
# How far below its held reading the gripper may be and still count as holding steady (0 open,
# 1 closed). Settled on droid_100 16 and droid_1.0.1 9, whose objects leave the fingers only as
# the gripper opens.
SETTLED = 0.05


@dataclass(frozen=True)
class _Grip:
    """Where the object was, frame by frame, while the gripper held steady."""

    holding: list[int]  # 5 fps frames with the gripper closed and steady
    out_of_hand: list[int]  # holding frames with no box, or a box far from the fingers
    from_fingers: dict[int, float | None]  # per frame, in box-widths; None with no box

    @property
    def in_hand(self) -> list[int]:
        return [f for f in self.holding if f not in self.out_of_hand]


def _fingers(track: Track) -> tuple[float, float]:
    """The wrist seed point, between the fingertips, in the track's pixels."""
    return (
        OBJECT_POINT[0] * track.width / RECIPE_SIZE[0],
        OBJECT_POINT[1] * track.height / RECIPE_SIZE[1],
    )


def _grip(stretch: Stretch, facts: EpisodeFacts, grasps: Grasps) -> _Grip:
    fingers, width = _fingers(stretch.track), median_width(stretch.track)
    from_fingers: dict[int, float | None] = {}
    for f in stretch.frames:
        box = stretch.boxes.get(f)
        from_fingers[f] = None if box is None else round(math.dist(centre(box), fingers) / width, 3)
    holding = _holding(stretch, facts, grasps)
    out = [f for f in holding if (d := from_fingers[f]) is None or d > FAR_WIDTHS]
    return _Grip(holding, out, from_fingers)


def _holding(stretch: Stretch, facts: EpisodeFacts, grasps: Grasps) -> list[int]:
    """Frames where the gripper is closed and holding steady: above the Rubric's closed level and
    within SETTLED of its median reading while closed. As it closes on the object or opens to let
    go, the object leaving the fingers is the grasp or the release, not a slip."""
    level = grasps.settings.gripper_closed_level.value
    gripper = facts.signals.gripper
    reading = {f: float(gripper[robot_frame(facts, stretch.time(f))]) for f in stretch.frames}
    closed = [f for f in stretch.frames if reading[f] > level]
    if not closed:
        return []
    held = statistics.median(reading[f] for f in closed)
    return [f for f in closed if reading[f] >= held - SETTLED]


def _measurement(grip: _Grip, stretch: Stretch) -> Measurement:
    if not grip.holding:
        return Measurement(0.0, "0.0 s", [TextSpan(text="The gripper is never closed here.")], [])
    if not grip.out_of_hand:
        nearest = [(d, f) for f in grip.holding if (d := grip.from_fingers[f]) is not None]
        furthest, at = max(nearest)
        held = f"Between the fingers while the gripper was closed: at most {furthest:.1f}"
        evidence = [
            TextSpan(text=f"{held} box-widths from them, at "),
            *at_times([stretch.time(at)]),
            TextSpan(text="."),
        ]
        return Measurement(0.0, "0.0 s", evidence, [])
    lost_s = round(len(grip.out_of_hand) / stretch.track.fps, 3)
    first = stretch.time(grip.out_of_hand[0])
    evidence = [
        TextSpan(text=f"Gone, or over {FAR_WIDTHS:g} box-widths from the fingers, for "),
        TextSpan(text=f"{seconds(lost_s)} while the gripper was closed, from "),
        *at_times([first]),
        TextSpan(text="."),
    ]
    return Measurement(lost_s, seconds(lost_s), evidence, [Moment(t=first, label="Lost")], first)


def in_hand_lost_s(
    criterion: Criterion, facts: EpisodeFacts, grasps: Grasps, window: Interval
) -> Measurement:
    track = facts.wrist
    if track is None:
        return no_track("wrist", "the wrist view hasn't been tracked.")
    stretch = Stretch.read(track, facts, window.start, window.end)
    grip = _grip(stretch, facts, grasps)
    plot = stretch.plot("Object from the fingers", "box-widths", FAR_WIDTHS, grip.from_fingers)
    measured = _measurement(grip, stretch)
    if grip.holding and not grip.in_hand:
        why = TextSpan(text=" Unsure: SAM never found the object between the fingers.")
        evidence = [*measured.evidence, why]
        unsure = replace(measured, evidence=evidence, status="unsure", uncertainty="track lost")
        return replace(unsure, plot=plot)
    if not grip.in_hand:
        return replace(measured, plot=plot)
    return stretch.judged(measured, plot, range(stretch.frames.start, grip.in_hand[-1] + 1))
