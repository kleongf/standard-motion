from typing import Annotated

from fastapi import APIRouter, Depends

from standard_motion.core.context import AppContext, get_context
from standard_motion.reference_labels.gate import revealed_episodes
from standard_motion.review.models import ReviewQueue
from standard_motion.review.service import review_queue

router = APIRouter(tags=["review"])

Context = Annotated[AppContext, Depends(get_context)]


@router.get("/review")
async def get_review_queue(ctx: Context) -> ReviewQueue:
    """The Needs review Episodes with a Reference label outside the Test set, least confident
    first; answer one with a `review` label."""
    return review_queue(ctx, revealed_episodes(ctx))
