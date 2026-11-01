from typing import Annotated

from fastapi import APIRouter, Depends, status

from winnow.core.context import AppContext, get_context
from winnow.export.history import past_exports
from winnow.export.models import ExportPreview, ExportRequest, ExportStarted, Include, PastExport
from winnow.export.preview import export_preview
from winnow.export.service import start_export

router = APIRouter(tags=["export"])

Context = Annotated[AppContext, Depends(get_context)]


@router.post("/export", status_code=status.HTTP_202_ACCEPTED)
async def post_export(request: ExportRequest, ctx: Context) -> ExportStarted:
    """Export in the background: every Episode outside the Test set, by its Triage decision,
    whether Reference-labelled or not, the Keeps only or with the Needs review Episodes too. A
    LeRobot v3.0 dataset per source, with rejections.jsonl holding the Reason for each Episode
    left out and manifest.json what was exported and why. The job has an item per Episode, then
    one that finishes the export and names its new folder under the data dir's exports/."""
    return ExportStarted(job_id=start_export(ctx, request.include))


@router.get("/export/preview")
async def get_export_preview(ctx: Context, include: Include = "keep") -> ExportPreview:
    """What an export would hold, per source: the Reference-labelled Episodes by Triage
    decision, how many aren't labelled yet (exporting shows their decisions, so the UI warns
    first) and how many are in the Test set, never exported."""
    return export_preview(ctx, include)


@router.get("/export/past")
async def get_past_exports(ctx: Context) -> list[PastExport]:
    """The exports under the data dir's exports/, newest first."""
    return past_exports(ctx.settings.data_dir / "exports")
