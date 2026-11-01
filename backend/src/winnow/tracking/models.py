from typing import Literal

from pydantic import BaseModel

from winnow.boxes.models import ExteriorCamera

# "wrist": seeded from robot data; "exterior": seeded from the hand-drawn box, in its view
TrackKind = Literal["wrist", "exterior"]


class TrackBox(BaseModel):
    """SAM's box on one frame of the 5 fps clip, in that clip's pixels (half-open bounds)."""

    frame: int
    left: float
    top: float
    right: float
    bottom: float


class TrackHealth(BaseModel):
    """Signs SAM lost the object, recomputed on every read. SAM's confidence is never used."""

    area_jumps: list[int]  # frames whose box area is over 4x the track's median
    centre_jumps: list[int]  # frames whose centre moved over one box-width from the frame before
    missing_fraction: float  # share of frames with no box
    lost: bool  # any area or centre jump, or no box on over 20% of frames


class Track(BaseModel):
    episode_id: str
    kind: TrackKind
    camera: str
    # "no_closure": the gripper never closed, so there was nothing to seed; recorded, not failed
    status: Literal["tracked", "no_closure"]
    fps: float
    frames: int  # in the 5 fps clip
    width: int
    height: int
    seed_frame: int | None
    boxes: list[TrackBox]
    health: TrackHealth | None  # None without a track


class FrameBox(BaseModel):
    """A box on frame 0, in that frame's pixels (half-open bounds)."""

    left: float
    top: float
    right: float
    bottom: float


# "found": SAM found the target, or the curator drew it; "not_found": SAM found nothing;
# "no_instruction" / "no_target": nothing to prompt SAM with. All but "found" are recorded, not
# failed, and leave placement unsure until a target box is drawn.
TargetStatus = Literal["found", "not_found", "no_instruction", "no_target"]


class TargetBox(BaseModel):
    """Where the object should end up, on frame 0 of the hand-drawn box's view: SAM's answer to
    a text prompt for the instruction's target, or the curator's box, which wins."""

    episode_id: str
    camera: ExteriorCamera
    origin: Literal["sam", "hand"]
    status: TargetStatus
    target: str | None  # the words SAM was prompted with
    box: FrameBox | None  # None unless found
    frame_width: int
    frame_height: int
    made_at: str
