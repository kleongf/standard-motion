from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from winnow.audit.models import AuditDraw, AuditSample
from winnow.audit.service import NothingToAuditError, audit_sample, draw_sample
from winnow.core.context import AppContext, get_context
from winnow.reference_labels.gate import revealed_episodes

router = APIRouter(tags=["audit"])

Context = Annotated[AppContext, Depends(get_context)]


@router.get("/audit")
async def get_audit(ctx: Context) -> AuditSample:
    """The latest Rubric version's Audit sample, each item's mark, and Keep precision. Mark an
    item with `audit` labels: pass on every Phrase is Good, a fail on any is Bad."""
    return audit_sample(ctx)


@router.post("/audit/sample", responses={409: {"description": "No auto-Keep to audit yet"}})
async def post_audit_sample(ctx: Context, body: AuditDraw | None = None) -> AuditSample:
    """Draws the Audit sample from the Episodes with a Reference label outside the Test set:
    once per Rubric version and margin multiplier s, so drawing again returns the stored one."""
    try:
        return draw_sample(ctx, revealed_episodes(ctx), (body or AuditDraw()).seed)
    except NothingToAuditError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
