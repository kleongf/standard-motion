from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from standard_motion.core.context import AppContext, get_context
from standard_motion.jobs.models import Job

router = APIRouter(tags=["jobs"])

Context = Annotated[AppContext, Depends(get_context)]


@router.get("/jobs/latest")
async def latest_job(kind: str, ctx: Context) -> Job | None:
    return ctx.jobs.latest(kind)


@router.get("/jobs/{job_id}")
async def get_job(job_id: int, ctx: Context) -> Job:
    job = ctx.jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No job {job_id}")
    return job
