from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from standard_motion.core.context import AppContext, get_context
from standard_motion.evaluation.disagreements import disagreements
from standard_motion.evaluation.models import EvaluationReport, EvaluationRequest, TestRun
from standard_motion.evaluation.protocol_models import Disagreement
from standard_motion.evaluation.service import UnknownRubricVersionError, run_evaluation

router = APIRouter(tags=["evaluation"])

Context = Annotated[AppContext, Depends(get_context)]


@router.post("/evaluation/runs")
async def post_evaluation_run(request: EvaluationRequest, ctx: Context) -> EvaluationReport:
    """Scores Standard Motion and the baselines against a set's Reference labels. A Test set run is
    appended to the Test run log; `standard-motion eval` returns the same report."""
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
    """Reference-labelled Episodes where Standard Motion's Triage decision, as the Workstation
    shows it now, differs from Spark alone's majority answer. Scored on every read, with no Meta
    call."""
    return disagreements(ctx)
