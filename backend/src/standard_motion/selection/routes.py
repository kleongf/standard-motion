from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from standard_motion.core.context import AppContext, get_context
from standard_motion.episodes.models import IngestStarted
from standard_motion.episodes.service import ingest_items
from standard_motion.selection.models import Candidate, Confirm, Decision
from standard_motion.selection.service import sheet_path

router = APIRouter(tags=["selection"])

Context = Annotated[AppContext, Depends(get_context)]


def _candidate(ctx: AppContext, episode_id: str) -> Candidate:
    candidate = ctx.selection.get(episode_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"{episode_id} isn't a selection candidate")
    return candidate


@router.get("/selection")
async def list_candidates(ctx: Context) -> list[Candidate]:
    return ctx.selection.list()


@router.get(
    "/selection/{episode_id}/sheet",
    response_class=FileResponse,
    responses={200: {"content": {"image/jpeg": {}}}},
)
async def get_sheet(episode_id: str, ctx: Context) -> FileResponse:
    candidate = _candidate(ctx, episode_id)
    path = sheet_path(ctx.settings.data_dir, candidate.source, candidate.index)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No contact sheet for {episode_id}")
    return FileResponse(path, media_type="image/jpeg")


@router.put("/selection/{episode_id}")
async def decide(episode_id: str, decision: Decision, ctx: Context) -> Candidate:
    _candidate(ctx, episode_id)
    if isinstance(decision, Confirm):
        candidate = ctx.selection.decide(episode_id, "confirmed", None)
    else:
        candidate = ctx.selection.decide(episode_id, "excluded", decision.reason)
    assert candidate is not None
    return candidate


@router.post("/selection/ingest", status_code=202)
async def ingest_confirmed(ctx: Context) -> IngestStarted:
    """Ingest every confirmed candidate, with the object and target Spark named."""
    confirmed = [c for c in ctx.selection.list() if c.status == "confirmed" and not c.ingested]
    if not confirmed:
        raise HTTPException(status_code=409, detail="No confirmed candidates left to ingest")
    tasks = {c.index: (c.object, c.target) for c in confirmed}
    items = ingest_items(
        confirmed[0].source, list(tasks), with_meta=ctx.meta is not None, tasks=tasks
    )
    return IngestStarted(job_id=ctx.runner.submit("ingest", items))
