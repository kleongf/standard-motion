from typing import Annotated

from fastapi import APIRouter, Depends

from winnow.core.context import AppContext, get_context
from winnow.reference_labels.gate import revealed_episodes
from winnow.review.models import ReviewQueue
from winnow.review.service import review_queue

router = APIRouter(tags=["review"])

Context = Annotated[AppContext, Depends(get_context)]


@router.get("/review")
async def get_review_queue(ctx: Context) -> ReviewQueue:
    """The Needs review Episodes with a Reference label outside the Test set, least confident
    first; answer one with a `review` label."""
    return review_queue(ctx, revealed_episodes(ctx))
