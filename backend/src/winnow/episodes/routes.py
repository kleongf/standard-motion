from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from winnow.core.context import AppContext, get_context
from winnow.episodes.models import Episode, IngestRequest, IngestStarted, Signals
from winnow.episodes.service import frame_zero, ingest_items, workstation_signals
from winnow.episodes.store import clip_path
from winnow.reference_labels.gate import listed_episodes

router = APIRouter(tags=["episodes"])

Context = Annotated[AppContext, Depends(get_context)]


@router.get("/episodes")
async def list_episodes(ctx: Context) -> list[Episode]:
    """The Dataset outcome stays hidden until an Episode's first-pass Reference label, so it
    can't anchor the labeller."""
    return listed_episodes(ctx)


def find_episode(ctx: AppContext, episode_id: str) -> Episode:
    episode = ctx.episodes.get(episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail=f"No Episode {episode_id}")
    return episode


@router.get("/episodes/{episode_id}/signals")
async def get_signals(episode_id: str, ctx: Context) -> Signals:
    episode = find_episode(ctx, episode_id)
    return workstation_signals(ctx.episodes.load_signals(episode))


@router.get(
    "/episodes/{episode_id}/clips/{camera}",
    response_class=FileResponse,
    responses={200: {"content": {"video/mp4": {}}}},
)
async def get_clip(episode_id: str, camera: str, ctx: Context) -> FileResponse:
    episode = find_episode(ctx, episode_id)
    if camera not in episode.cameras:
        raise HTTPException(status_code=404, detail=f"No {camera} clip for {episode_id}")
    path = clip_path(ctx.episodes.episode_folder(episode), camera)
    return FileResponse(path, media_type="video/mp4")


@router.get(
    "/episodes/{episode_id}/frame0/{camera}",
    response_class=FileResponse,
    responses={200: {"content": {"image/jpeg": {}}}},
)
async def get_frame0(episode_id: str, camera: str, ctx: Context) -> FileResponse:
    episode = find_episode(ctx, episode_id)
    if camera not in episode.cameras:
        raise HTTPException(status_code=404, detail=f"No {camera} clip for {episode_id}")
    return FileResponse(await frame_zero(ctx.episodes, episode, camera), media_type="image/jpeg")


@router.post("/episodes/ingest", status_code=status.HTTP_202_ACCEPTED)
async def start_ingest(request: IngestRequest, ctx: Context) -> IngestStarted:
    items = ingest_items(request.source, request.indices, with_meta=ctx.meta is not None)
    return IngestStarted(job_id=ctx.runner.submit("ingest", items))
