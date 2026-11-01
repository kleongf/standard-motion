"""Synthetic SAM tracks and tracked Criteria for scoring-function tests.

Tracks are 5 fps over the 3 s (45-frame, 15 Hz) synthetic Episodes of `robot_data`, in a 320x180
clip. With CLEAN_GRIPPER the grasp closes on 5 fps frames 5-9 (1.0-1.9 s) and opens at 2.0 s.
"""

from collections.abc import Iterable
from dataclasses import replace

from tests.triage.robot_data import SETTINGS
from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.models import Criterion, Window
from winnow.rubric.models import Rubric
from winnow.tracking.models import FrameBox, TargetBox, Track, TrackBox, TrackKind

FRAMES = 15  # 5 fps over 3 s
FINGERS = (190.0, 105.0)  # the wrist seed point, between the fingertips, in a 320x180 clip
DROPS = "never drops it"
PLACES = "places it on the target"


def box_at(frame: int, centre: tuple[float, float], size: float = 40) -> TrackBox:
    x, y = centre
    half = size / 2
    return TrackBox(frame=frame, left=x - half, top=y - half, right=x + half, bottom=y + half)


def track(kind: TrackKind, boxes: Iterable[TrackBox]) -> Track:
    return Track(
        episode_id="droid_100:0",
        kind=kind,
        camera="wrist_image_left" if kind == "wrist" else "exterior_image_2_left",
        status="tracked",
        fps=5.0,
        frames=FRAMES,
        width=320,
        height=180,
        seed_frame=5,
        boxes=list(boxes),
        health=None,
    )


def held(frames: Iterable[int] = range(FRAMES)) -> Track:
    """The wrist object track of an object sitting between the fingers on `frames`."""
    return track("wrist", (box_at(f, FINGERS) for f in frames))


def target(left: float, top: float, right: float, bottom: float) -> TargetBox:
    """A target box on frame 0 of the exterior view, drawn on a 640x360 frame: twice the clip's
    size, so placement must scale it."""
    return TargetBox(
        episode_id="droid_100:0",
        camera="exterior_image_2_left",
        origin="hand",
        status="found",
        target="pot",
        box=FrameBox(left=2 * left, top=2 * top, right=2 * right, bottom=2 * bottom),
        frame_width=640,
        frame_height=360,
        made_at="2026-10-30T00:00:00+00:00",
    )


def in_hand(window: Window | None = None) -> Criterion:
    return Criterion(
        id="in-hand",
        phrase=DROPS,
        primitive="in_hand_lost_s",
        comparator="<",
        threshold=0.4,
        unit="s",
        window=window or Window(kind="holding"),
    )


def fall() -> Criterion:
    return Criterion(
        id="fall",
        phrase=DROPS,
        primitive="fall_after_release",
        comparator="<=",
        threshold=0.5,
        unit="box-heights",
    )


def overlap() -> Criterion:
    return Criterion(
        id="overlap",
        phrase=PLACES,
        primitive="final_overlap",
        comparator=">=",
        threshold=0.5,
        unit="ratio",
        window=Window(kind="last_n_s", seconds=1.0),
    )


def rubric(*criteria: Criterion) -> Rubric:
    return Rubric(
        description=f"Expert: {DROPS}, {PLACES}.",
        phrases=[DROPS, PLACES],
        settings=SETTINGS,
        criteria=list(criteria),
    )


def with_tracks(
    facts: EpisodeFacts,
    wrist: Track | None = None,
    exterior: Track | None = None,
    target_box: TargetBox | None = None,
) -> EpisodeFacts:
    return replace(facts, wrist=wrist, exterior=exterior, target=target_box)
