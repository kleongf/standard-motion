from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from winnow.boxes.models import FrameRect
from winnow.boxes.service import InvalidBoxError, check_box
from winnow.core.context import AppContext, get_context
from winnow.episodes.routes import find_episode
from winnow.tracking.models import TargetBox, Track
from winnow.tracking.target import chosen_target_boxes, draw_target_box

router = APIRouter(tags=["tracking"])

Context = Annotated[AppContext, Depends(get_context)]


@router.get("/episodes/{episode_id}/tracks")
async def get_tracks(episode_id: str, ctx: Context) -> list[Track]:
    """The Episode's SAM tracks so far, each with its health; empty before any has run."""
    return ctx.tracks.for_episode(find_episode(ctx, episode_id).id)


@router.get("/target-boxes")
async def list_target_boxes(ctx: Context) -> list[TargetBox]:
    """Each boxed Episode's target box so far: the hand-drawn one if any, else SAM's."""
    return chosen_target_boxes(ctx.targets, ctx.boxes.list())


@router.put("/episodes/{episode_id}/target-box")
async def put_target_box(episode_id: str, draw: FrameRect, ctx: Context) -> TargetBox:
    """Draw the target box by hand, on frame 0 of the view the object was boxed in. It replaces
    SAM's for as long as the object box stays on that view."""
    episode = find_episode(ctx, episode_id)
    box = ctx.boxes.get(episode.id)
    if box is None:
        detail = "Box the object first: the target box goes on the same view"
        raise HTTPException(status_code=409, detail=detail)
    try:
        check_box(draw, (box.frame_width, box.frame_height))
    except InvalidBoxError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return draw_target_box(ctx.targets, episode, box, draw)
