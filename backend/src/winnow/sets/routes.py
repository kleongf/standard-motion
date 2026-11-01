from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from winnow.core.context import AppContext, get_context
from winnow.sets.models import EpisodeSet, FreezeRequest, FreezeWarnings, SetMembers, SetName
from winnow.sets.service import (
    FreezeWarningsError,
    NotInSetError,
    SetConflictError,
    SetError,
    add_episodes,
    freeze,
    remove_episode,
)

router = APIRouter(tags=["sets"])

Context = Annotated[AppContext, Depends(get_context)]


def _status(error: SetError) -> int:
    if isinstance(error, SetConflictError):
        return 409
    if isinstance(error, NotInSetError):
        return 404
    return 422


def _answer(change: Callable[[], EpisodeSet]) -> EpisodeSet:
    try:
        return change()
    except SetError as error:
        raise HTTPException(status_code=_status(error), detail=str(error)) from error


@router.get("/sets")
async def list_sets(ctx: Context) -> list[EpisodeSet]:
    return ctx.sets.list()


@router.post("/sets/{name}/episodes")
async def post_set_episodes(name: SetName, members: SetMembers, ctx: Context) -> EpisodeSet:
    return _answer(lambda: add_episodes(ctx.sets, ctx.episodes, name, members.episode_ids))


@router.delete("/sets/{name}/episodes/{episode_id}")
async def delete_set_episode(name: SetName, episode_id: str, ctx: Context) -> EpisodeSet:
    return _answer(lambda: remove_episode(ctx.sets, name, episode_id))


@router.post(
    "/sets/{name}/freeze", response_model=EpisodeSet, responses={409: {"model": FreezeWarnings}}
)
async def post_freeze(
    name: SetName, ctx: Context, request: FreezeRequest | None = None
) -> EpisodeSet | JSONResponse:
    """409 with the protocol warnings unless `force`; other refusals are plain errors."""
    try:
        return freeze(ctx.sets, name, force=request is not None and request.force)
    except FreezeWarningsError as error:
        body = FreezeWarnings(detail=str(error), warnings=error.warnings)
        return JSONResponse(body.model_dump(), status_code=409)
    except SetError as error:
        raise HTTPException(status_code=_status(error), detail=str(error)) from error
