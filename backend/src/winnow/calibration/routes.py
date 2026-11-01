from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from winnow.calibration.models import AcceptedSuggestion, Calibration
from winnow.calibration.service import (
    NoLabelsError,
    NoSuggestionError,
    accept_suggestion,
    calibrate,
    calibration,
)
from winnow.core.context import AppContext, get_context

router = APIRouter(tags=["calibration"])

Context = Annotated[AppContext, Depends(get_context)]


@router.get("/calibration")
async def get_calibration(ctx: Context) -> Calibration:
    """The latest Rubric version's margin multiplier s (1 until calibrated) and the thresholds
    the anchor pool's interview and review labels suggest for it now."""
    return calibration(ctx)


@router.post(
    "/calibration/run",
    responses={409: {"description": "No interview or review label on the anchor pool yet"}},
)
async def post_calibration_run(ctx: Context) -> Calibration:
    """Scans s ∈ {2, 1.5, 1, 0.75, 0.5}, widest first, on the anchor pool's labelled
    (Episode, Phrase) pairs, keeps the last whose errors' one-sided Clopper–Pearson upper bound
    is at most 0.2 at 90%, checks whether dropping 2 labels moves it, and scores the latest
    Rubric version with it from now on."""
    try:
        return calibrate(ctx)
    except NoLabelsError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post(
    "/calibration/suggestions/{criterion_id}/accept",
    status_code=status.HTTP_201_CREATED,
    responses={404: {"description": "Labels suggest no threshold for this Criterion"}},
)
async def post_accept_suggestion(criterion_id: str, ctx: Context) -> AcceptedSuggestion:
    """Freezes the latest Rubric version with the suggested threshold and margin as the next
    version, which keeps the s it was calibrated with, and applies them to the draft too unless
    the draft's Criterion now compares differently; the reply says which."""
    try:
        return accept_suggestion(ctx, criterion_id)
    except NoSuggestionError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
