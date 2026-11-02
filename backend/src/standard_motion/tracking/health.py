"""Tracking health: the three patterns a lost SAM track leaves in its boxes.

Fixed constants, re-checked on the Dev set. SAM's confidence is no loss signal (it was 0.92 on a
box swollen over the whole arm), so it is never used.
"""

import math
import statistics
from collections.abc import Sequence

from standard_motion.tracking.models import TrackBox, TrackHealth

AREA_JUMP_RATIO = 4.0  # a box over 4x the track's median area has bled onto something else
CENTRE_JUMP_WIDTHS = 1.0  # a centre moving over one box-width in one 5 fps frame has jumped
MISSING_FRACTION = 0.2  # no box on over 20% of frames


def _area(box: TrackBox) -> float:
    return (box.right - box.left) * (box.bottom - box.top)


def _centre(box: TrackBox) -> tuple[float, float]:
    return ((box.left + box.right) / 2, (box.top + box.bottom) / 2)


def track_health(
    boxes: Sequence[TrackBox], frames: int, window: range | None = None
) -> TrackHealth:
    """Health over `window` (frames of the 5 fps clip; the whole track by default). The median
    area is always the whole track's, so a window spent bleeding still stands out."""
    window = window if window is not None else range(frames)
    by_frame = {box.frame: box for box in boxes}
    median = statistics.median(_area(b) for b in boxes) if boxes else 0.0
    inside = [by_frame[f] for f in window if f in by_frame]
    area_jumps = [b.frame for b in inside if median > 0 and _area(b) > AREA_JUMP_RATIO * median]
    centre_jumps: list[int] = []
    for box in inside:
        before = by_frame.get(box.frame - 1)
        if before is None or box.frame - 1 not in window:
            continue
        moved = math.dist(_centre(before), _centre(box))
        if moved > CENTRE_JUMP_WIDTHS * (before.right - before.left):
            centre_jumps.append(box.frame)
    missing = 1 - len(inside) / len(window) if len(window) else 0.0
    return TrackHealth(
        area_jumps=area_jumps,
        centre_jumps=centre_jumps,
        missing_fraction=round(missing, 4),
        lost=bool(area_jumps or centre_jumps or missing > MISSING_FRACTION),
    )
