from typing import Annotated

from fastapi import APIRouter, Depends, status

from winnow.core.context import AppContext, get_context
from winnow.export.models import ExportScope, ExportStarted
from winnow.export.plan import export_scope
from winnow.export.service import start_export

router = APIRouter(tags=["export"])

Context = Annotated[AppContext, Depends(get_context)]


@router.post("/export", status_code=status.HTTP_202_ACCEPTED)
async def post_export(ctx: Context) -> ExportStarted:
    """Export the kept Episodes in the background: every Episode outside the Test set, by its
    Triage decision, whether Reference-labelled or not. A LeRobot v3.0 dataset per source, with
    rejections.jsonl holding the Reason for each Episode not kept. The finished job's item names
    the new folder under the data dir's exports/."""
    return ExportStarted(job_id=start_export(ctx))


@router.get("/export/scope")
async def get_export_scope(ctx: Context) -> ExportScope:
    """How many Episodes an export would decide on, and how many of them aren't
    Reference-labelled yet: exporting shows their decisions, so the UI warns first."""
    return export_scope(ctx)
