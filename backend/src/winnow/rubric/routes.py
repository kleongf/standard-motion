from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from winnow.core.context import AppContext, get_context
from winnow.rubric.anchor_pool import AnchorPool, anchor_pool
from winnow.rubric.edits import UnknownCriterionError
from winnow.rubric.models import (
    DESCRIPTION_MAX,
    AnchorPreview,
    DraftEdit,
    RubricDraft,
    RubricVersion,
)
from winnow.rubric.service import (
    DraftChangedError,
    MetaUnavailableError,
    NoDraftError,
    compile_draft,
    edit_draft,
    preview_draft,
    preview_version,
    run_draft,
)

router = APIRouter(tags=["rubric"])

Context = Annotated[AppContext, Depends(get_context)]

NO_DRAFT: dict[int | str, dict[str, object]] = {
    404: {"description": "No Description has been compiled yet"},
    422: {"description": "The draft has no such Criterion"},
}


class CompileRequest(BaseModel):
    description: str = Field(min_length=1, max_length=DESCRIPTION_MAX)
    # Compile every Phrase anew, discarding the draft's Criteria, edits and interview.
    fresh: bool = False


@router.get("/rubric")
async def get_rubric(ctx: Context) -> RubricVersion:
    """The latest Rubric version: the one every Episode is scored against."""
    return ctx.rubrics.latest()


@router.get("/rubric/versions")
async def list_versions(ctx: Context) -> list[RubricVersion]:
    """Every Rubric version, newest first."""
    return ctx.rubrics.list()


@router.get(
    "/rubric/versions/{version}/preview",
    responses={404: {"description": "No such Rubric version"}},
)
async def get_version_preview(version: int, ctx: Context) -> AnchorPreview:
    """A frozen Rubric version scored on the anchor pool."""
    found = ctx.rubrics.get(version)
    if found is None:
        raise HTTPException(status_code=404, detail=f"No Rubric version {version}")
    return preview_version(ctx, found)


@router.get("/rubric/draft")
async def get_draft(ctx: Context) -> RubricDraft | None:
    """The Rubric draft on the Describe page; null until a Description is compiled."""
    return ctx.drafts.get()


@router.post(
    "/rubric/draft/compile",
    responses={
        409: {"description": "The Description changed while Spark read the edit"},
        502: {"description": "Spark's answer couldn't be used"},
        503: {"description": "The Meta API isn't configured"},
    },
)
async def post_compile(request: CompileRequest, ctx: Context) -> RubricDraft:
    """Compile a Description into the Rubric draft: one Spark call, plus one repair turn when its
    answer fails code's checks. An edit of the draft's Description compiles only the changed
    Phrases, keeping the rest with their Criteria; `fresh` compiles all of it."""
    description = request.description.strip()
    try:
        return await compile_draft(ctx, description, request.fresh)
    except MetaUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except DraftChangedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RuntimeError as error:  # the Meta API failed, or its answer couldn't be read
        raise HTTPException(status_code=502, detail=f"Compile failed: {error}") from error


def _on_draft[T](act: Callable[[], T]) -> T:
    try:
        return act()
    except NoDraftError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except UnknownCriterionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.patch("/rubric/draft", responses=NO_DRAFT)
async def patch_draft(edit: DraftEdit, ctx: Context) -> RubricDraft:
    """Direct edits on Criterion cards and the Rubric settings, saved; no model call."""
    return _on_draft(lambda: edit_draft(ctx, edit))


@router.post("/rubric/draft/preview", responses=NO_DRAFT)
async def post_preview(edit: DraftEdit, ctx: Context) -> AnchorPreview:
    """The draft, with `edit` applied but not saved, scored on the anchor pool: a threshold drag
    re-sorts it with no model call."""
    return _on_draft(lambda: preview_draft(ctx, edit))


@router.post("/rubric/draft/run", status_code=201, responses=NO_DRAFT)
async def post_run(ctx: Context) -> RubricVersion:
    """Freeze the draft into the next immutable Rubric version, which scores every Episode."""
    return _on_draft(lambda: run_draft(ctx))


@router.get("/anchor-pool")
async def get_anchor_pool(ctx: Context) -> AnchorPool:
    """The Episodes the Rubric is written against: the Dev set, never the Test set."""
    return anchor_pool(ctx)
