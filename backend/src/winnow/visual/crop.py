"""Where a visual Criterion's clip comes from: one view, the Criterion's window padded a little,
and for placement the object's final box joined with the target box, enlarged.

The window comes from measured events (the grasp and the release, `criteria.windows`); tracked
events can narrow it here once they exist. Clips are named by a hash of what they show, so
cutting the same clip again finds it already there and its Meta calls stay cache hits.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from winnow.criteria.grasps import Interval
from winnow.criteria.models import Criterion
from winnow.episodes.clips import cut_cropped
from winnow.tracking.models import FrameBox, TargetBox, Track
from winnow.visual.models import VisualClip

PAD_S = 0.5  # either side of the window, so Spark sees what leads in and out
MIN_CLIP_S = 1.0
ENLARGE = 1.5  # the joined box grows by this about its centre, for context
MIN_SIDE = 0.25  # of the frame, so a small object still shows its surroundings
CLIP_VERSION = 1  # bump when cutting changes, so every clip is cut (and asked) again
DEFAULT_VIEW = "exterior_image_1_left"


@dataclass(frozen=True)
class Placement:
    """What a placement crop is made from: the view the object was boxed in, its track there,
    and the target box on frame 0 of that view."""

    camera: str
    track: Track | None
    target: TargetBox | None


@dataclass(frozen=True)
class CropPlan:
    camera: str
    start: float  # s
    end: float
    box: FrameBox | None  # in fractions of the frame (0 to 1); None for the whole view


def _fractions(box: FrameBox, width: float, height: float) -> FrameBox:
    return FrameBox(
        left=box.left / width,
        top=box.top / height,
        right=box.right / width,
        bottom=box.bottom / height,
    )


def final_object_box(track: Track, end_s: float) -> FrameBox | None:
    """The object's last tracked box at or before `end_s`, in fractions of the frame."""
    seen = [b for b in track.boxes if b.frame / track.fps <= end_s + 1e-6]
    if not seen:
        return None
    last = seen[-1]
    box = FrameBox(left=last.left, top=last.top, right=last.right, bottom=last.bottom)
    return _fractions(box, track.width, track.height)


def _grown(low: float, high: float) -> tuple[float, float]:
    centre, half = (low + high) / 2, max((high - low) * ENLARGE, MIN_SIDE) / 2
    low, high = centre - half, centre + half
    if low < 0:
        low, high = 0.0, high - low
    if high > 1:
        low, high = max(0.0, low - (high - 1)), 1.0
    return low, high


def joined(*boxes: FrameBox) -> FrameBox:
    """The smallest box holding every box, enlarged about its centre and kept in the frame."""
    left, right = _grown(min(b.left for b in boxes), max(b.right for b in boxes))
    top, bottom = _grown(min(b.top for b in boxes), max(b.bottom for b in boxes))
    return FrameBox(left=left, top=top, right=right, bottom=bottom)


def _placement_box(placement: Placement, end_s: float) -> FrameBox | None:
    track, target = placement.track, placement.target
    if track is None or target is None or target.box is None:
        return None
    final = final_object_box(track, end_s)
    if final is None:
        return None
    return joined(final, _fractions(target.box, target.frame_width, target.frame_height))


def plan_crop(
    criterion: Criterion, t: list[float], window: Interval, placement: Placement | None
) -> CropPlan:
    """`t` is each robot-data frame's time from the Episode's start; `window` the Criterion's
    frames. Without a box, target box or track, a placement crop shows the whole view."""
    end = min(t[-1], t[window.end] + PAD_S)
    start = max(0.0, min(t[window.start] - PAD_S, end - MIN_CLIP_S))
    if criterion.crop == "placement" and placement is not None:
        return CropPlan(placement.camera, start, end, _placement_box(placement, end))
    camera = criterion.views[0] if criterion.views else DEFAULT_VIEW
    return CropPlan(camera, start, end, None)


def clips_folder(episode_folder: Path) -> Path:
    """Where an Episode's visual clips live."""
    return episode_folder / "visual"


def _even(value: float) -> int:
    return max(2, int(value) // 2 * 2)  # yuv420p needs even sides


def _pixels(box: FrameBox, size: tuple[int, int]) -> tuple[int, int, int, int]:
    width, height = size
    left, top = _even(box.left * width), _even(box.top * height)
    left, top = min(left, width - 2), min(top, height - 2)
    crop_w = min(_even((box.right - box.left) * width), width - left)
    crop_h = min(_even((box.bottom - box.top) * height), height - top)
    return left, top, crop_w, crop_h


def cut(
    episode_id: str, plan: CropPlan, source: Path, size: tuple[int, int], folder: Path
) -> tuple[VisualClip, bool]:
    """The plan's clip of `source` (whose frames are `size`) in `folder`, cut unless it already
    is there; returns it and whether it was cut now."""
    crop = _pixels(plan.box, size) if plan.box else None
    box = None
    if crop:
        left, top, w, h = crop
        box = FrameBox(left=left, top=top, right=left + w, bottom=top + h)
    spec = [CLIP_VERSION, episode_id, plan.camera, round(plan.start, 3), round(plan.end, 3), crop]
    name = hashlib.sha256(json.dumps(spec).encode()).hexdigest()[:16] + ".mp4"
    clip = VisualClip(
        name=name, camera=plan.camera, start=round(plan.start, 3), end=round(plan.end, 3), box=box
    )
    out = folder / name
    if out.exists():
        return clip, False
    cut_cropped(source, plan.start, plan.end, crop, out)
    return clip, True
