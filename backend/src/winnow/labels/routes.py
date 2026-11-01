from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from winnow.core.context import AppContext, get_context
from winnow.labels.models import LabelDraw, StoredLabel
from winnow.labels.service import UnknownPhraseError, save_label
from winnow.reference_labels.gate import HIDDEN_UNTIL_LABELLED, RevealedEpisode

router = APIRouter(tags=["labels"])

Context = Annotated[AppContext, Depends(get_context)]


@router.post(
    "/episodes/{episode_id}/labels",
    status_code=status.HTTP_201_CREATED,
    responses=HIDDEN_UNTIL_LABELLED,
)
async def post_label(episode: RevealedEpisode, draw: LabelDraw, ctx: Context) -> StoredLabel:
    """Overrides one Phrase's result for this Episode; its Triage decision recomputes."""
    try:
        return save_label(ctx, episode.id, draw)
    except UnknownPhraseError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/episodes/{episode_id}/labels", responses=HIDDEN_UNTIL_LABELLED)
async def list_labels(episode: RevealedEpisode, ctx: Context) -> list[StoredLabel]:
    """Every label the Episode was given, oldest first; the newest per Phrase is in force."""
    return ctx.labels.history(episode.id)
