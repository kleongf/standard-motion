from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from winnow.core.context import AppContext, get_context
from winnow.interview.models import AnswerDraw, Interview, TextDraw, TextReply
from winnow.interview.service import (
    StaleQuestionError,
    UnknownAnswerError,
    answer,
    current,
    undo,
)
from winnow.interview.text import answer_text
from winnow.labels.service import UnknownPhraseError
from winnow.rubric.service import DraftChangedError, MetaUnavailableError, NoDraftError
from winnow.visual.service import dry_run

router = APIRouter(tags=["interview"])

Context = Annotated[AppContext, Depends(get_context)]

NO_DRAFT: dict[int | str, dict[str, object]] = {
    404: {"description": "No Description has been compiled yet, or no such answer"},
}


def _on_interview(act: Callable[[], Interview]) -> Interview:
    try:
        return act()
    except (NoDraftError, UnknownAnswerError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (StaleQuestionError, UnknownPhraseError) as error:  # the draft changed meanwhile
        raise HTTPException(status_code=409, detail=str(error)) from error


def _queue_dry_run(ctx: AppContext) -> None:
    """Asks Spark, in the background, what an answer left unanswered of the draft's visual
    Criteria on the anchor pool: a settled grasp setting, an undo or a recompile can each
    change what is asked."""
    draft = ctx.drafts.get()
    if draft is not None:
        dry_run(ctx, draft)


@router.get("/interview", responses=NO_DRAFT)
async def get_interview(ctx: Context) -> Interview:
    """The interview on the Rubric draft: the answered cards and the question code asks next."""
    return _on_interview(lambda: current(ctx))


@router.post(
    "/interview/answers",
    responses={**NO_DRAFT, 409: {"description": "Not the question being asked"}},
)
async def post_answer(draw: AnswerDraw, ctx: Context) -> Interview:
    """Answer the question being asked. A threshold answer is also an interview label on the
    anchor Episode's Phrase; the answer that settles a threshold changes the Criterion."""
    answered = _on_interview(lambda: answer(ctx, draw))
    _queue_dry_run(ctx)
    return answered


@router.post(
    "/interview/text",
    responses={
        **NO_DRAFT,
        409: {"description": "Not the question being asked, or the draft changed meanwhile"},
        502: {"description": "Spark failed, or its reading of the words couldn't be used"},
        503: {"description": "The Meta API isn't configured"},
    },
)
async def post_text(draw: TextDraw, ctx: Context) -> TextReply:
    """The curator's own words, read by Spark: to the question being asked, they pick one of its
    answers, or recompile only the Phrase it asks about with them; with no question, they edit
    the Description, which recompiles as an edit does. Template answers never ask a model."""
    try:
        reply = await answer_text(ctx, draw)
    except MetaUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except NoDraftError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (StaleQuestionError, UnknownPhraseError, DraftChangedError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RuntimeError as error:  # the Meta API failed, or its answer couldn't be read
        detail = f"Reading your words failed: {error}"
        raise HTTPException(status_code=502, detail=detail) from error
    _queue_dry_run(ctx)
    return reply


@router.delete("/interview/answers/{answer_id}", responses=NO_DRAFT)
async def delete_answer(answer_id: int, ctx: Context) -> Interview:
    """Undo an answer, and the later ones on the same question: the draft gets back what they
    changed, and their labels are withdrawn."""
    undone = _on_interview(lambda: undo(ctx, answer_id))
    _queue_dry_run(ctx)
    return undone
