"""Hand-drawn boxes: one per Episode, around the task object on frame 0 of an exterior view.
They seed the exterior object track that placement Criteria read."""

from typing import Literal

from pydantic import BaseModel

ExteriorCamera = Literal["exterior_image_1_left", "exterior_image_2_left"]


class FrameRect(BaseModel):
    """A box in frame-0 pixels."""

    x1: int
    y1: int
    x2: int
    y2: int


class BoxDraw(FrameRect):
    """A box in frame-0 pixels of the chosen view."""

    camera: ExteriorCamera


class Box(BoxDraw):
    episode_id: str
    frame_width: int
    frame_height: int
    drawn_at: str
