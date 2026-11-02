from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from standard_motion.audit.routes import router as audit_router
from standard_motion.boxes.routes import router as boxes_router
from standard_motion.calibration.routes import router as calibration_router
from standard_motion.core.context import build_context
from standard_motion.core.routes import router as core_router
from standard_motion.core.settings import Settings, get_settings
from standard_motion.dataset.routes import router as dataset_router
from standard_motion.episodes.routes import router as episodes_router
from standard_motion.evaluation.routes import router as evaluation_router
from standard_motion.export.routes import router as export_router
from standard_motion.interview.routes import router as interview_router
from standard_motion.jobs.routes import router as jobs_router
from standard_motion.labels.routes import router as labels_router
from standard_motion.meta.transport import Transport
from standard_motion.reference_labels.routes import router as reference_labels_router
from standard_motion.review.routes import router as review_router
from standard_motion.rubric.routes import router as rubric_router
from standard_motion.selection.routes import router as selection_router
from standard_motion.sets.routes import router as sets_router
from standard_motion.tracking.routes import router as tracking_router
from standard_motion.triage.routes import router as triage_router
from standard_motion.visual.routes import router as visual_router
from standard_motion.voice.routes import router as voice_router


def create_app(settings: Settings | None = None, transport: Transport | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        ctx = build_context(settings or get_settings(), transport)
        ctx.jobs.fail_interrupted()
        app.state.context = ctx
        yield
        await ctx.runner.shutdown()
        ctx.db.close()

    app = FastAPI(title="Standard Motion", lifespan=lifespan)
    for router in (
        core_router,
        dataset_router,
        episodes_router,
        boxes_router,
        selection_router,
        sets_router,
        tracking_router,
        rubric_router,
        interview_router,
        triage_router,
        reference_labels_router,
        labels_router,
        review_router,
        audit_router,
        calibration_router,
        evaluation_router,
        export_router,
        visual_router,
        voice_router,
        jobs_router,
    ):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
