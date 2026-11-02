from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from standard_motion.boxes.models import Box, BoxDraw
from standard_motion.boxes.service import InvalidBoxError, save_box
from standard_motion.core.context import AppContext, get_context
from standard_motion.episodes.routes import find_episode

router = APIRouter(tags=["boxes"])

Context = Annotated[AppContext, Depends(get_context)]


@router.get("/boxes")
async def list_boxes(ctx: Context) -> list[Box]:
    return ctx.boxes.list()


@router.put("/episodes/{episode_id}/box")
async def put_box(episode_id: str, draw: BoxDraw, ctx: Context) -> Box:
    episode = find_episode(ctx, episode_id)
    try:
        return await save_box(ctx, episode, draw)
    except InvalidBoxError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
