import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from winnow.core.context import AppContext, get_context
from winnow.visual.models import AskRequest, AskStarted
from winnow.visual.service import MetaUnavailableError, ask_visual, visual_clip

router = APIRouter(tags=["visual"])

Context = Annotated[AppContext, Depends(get_context)]

CLIP_NAME = re.compile(r"[0-9a-f]{16}\.mp4")


@router.post(
    "/visual/ask",
    status_code=status.HTTP_202_ACCEPTED,
    responses={503: {"description": "The Meta API isn't configured"}},
)
async def post_ask(request: AskRequest, ctx: Context) -> AskStarted:
    """Ask Spark the latest Rubric version's visual Criteria about each Episode, in the
    background: crop one clip per Criterion and Episode, then 3 samples about it. Asking again
    pays only for cache misses."""
    try:
        return AskStarted(job_id=ask_visual(ctx, ctx.rubrics.latest(), request.episode_ids))
    except MetaUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get(
    "/episodes/{episode_id}/visual-clips/{name}",
    response_class=FileResponse,
    responses={200: {"content": {"video/mp4": {}}}, 404: {"description": "No such clip"}},
)
async def get_visual_clip(episode_id: str, name: str, ctx: Context) -> FileResponse:
    """The clip a visual Criterion asked Spark about."""
    path = visual_clip(ctx, episode_id, name) if CLIP_NAME.fullmatch(name) else None
    if path is None:
        raise HTTPException(status_code=404, detail=f"No clip {name} for {episode_id}")
    return FileResponse(path, media_type="video/mp4")
