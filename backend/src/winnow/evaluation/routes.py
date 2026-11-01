from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from winnow.core.context import AppContext, get_context
from winnow.evaluation.disagreements import disagreements
from winnow.evaluation.models import EvaluationReport, EvaluationRequest, TestRun
from winnow.evaluation.protocol_models import Disagreement
from winnow.evaluation.service import UnknownRubricVersionError, run_evaluation

router = APIRouter(tags=["evaluation"])

Context = Annotated[AppContext, Depends(get_context)]


@router.post("/evaluation/runs")
async def post_evaluation_run(request: EvaluationRequest, ctx: Context) -> EvaluationReport:
    """Scores Winnow and the baselines against a set's Reference labels. A Test set run is
    appended to the Test run log; `winnow eval` returns the same report."""
    try:
        return run_evaluation(ctx, request)
    except UnknownRubricVersionError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/evaluation/test-runs")
async def list_test_runs(ctx: Context) -> list[TestRun]:
    """Every Test set run, newest first."""
    return ctx.test_runs.list()


@router.get("/evaluation/disagreements")
async def list_disagreements(ctx: Context) -> list[Disagreement]:
    """Reference-labelled Episodes where Winnow's Triage decision, as the Workstation shows it
    now, differs from Spark alone's majority answer. Scored on every read, with no Meta call."""
    return disagreements(ctx)
