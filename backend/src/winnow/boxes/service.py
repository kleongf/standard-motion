from PIL import Image

from winnow.boxes.models import Box, BoxDraw, FrameRect
from winnow.core.context import AppContext
from winnow.episodes.models import Episode
from winnow.episodes.service import frame_zero
from winnow.tracking.exterior import BOX_STEPS, box_items

MIN_SIDE_PX = 3  # smaller than this, SAM has nothing to track


class InvalidBoxError(ValueError):
    pass


def check_box(draw: FrameRect, frame_size: tuple[int, int]) -> None:
    width, height = frame_size
    if not (0 <= draw.x1 < draw.x2 <= width and 0 <= draw.y1 < draw.y2 <= height):
        raise InvalidBoxError(f"The box must lie inside the {width} by {height} px frame")
    if draw.x2 - draw.x1 < MIN_SIDE_PX or draw.y2 - draw.y1 < MIN_SIDE_PX:
        raise InvalidBoxError(f"Each side must be at least {MIN_SIDE_PX} px")


async def save_box(ctx: AppContext, episode: Episode, draw: BoxDraw) -> Box:
    still = await frame_zero(ctx.episodes, episode, draw.camera)
    with Image.open(still) as image:
        frame_size = image.size
    check_box(draw, frame_size)
    box = ctx.boxes.save(episode.id, draw, frame_size)
    queue_box_work(ctx, episode.id)
    return box


def queue_box_work(ctx: AppContext, episode_id: str, steps: tuple[str, ...] = BOX_STEPS) -> None:
    """Run the SAM steps a boxed Episode's box feeds; nothing without a box, or without Meta to
    run them."""
    if ctx.meta is not None and ctx.boxes.get(episode_id) is not None:
        ctx.runner.submit("box", box_items(episode_id, steps))
