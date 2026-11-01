from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from winnow.audit.routes import router as audit_router
from winnow.boxes.routes import router as boxes_router
from winnow.calibration.routes import router as calibration_router
from winnow.core.context import build_context
from winnow.core.routes import router as core_router
from winnow.core.settings import Settings, get_settings
from winnow.dataset.routes import router as dataset_router
from winnow.episodes.routes import router as episodes_router
from winnow.evaluation.routes import router as evaluation_router
from winnow.export.routes import router as export_router
from winnow.interview.routes import router as interview_router
from winnow.jobs.routes import router as jobs_router
from winnow.labels.routes import router as labels_router
from winnow.meta.transport import Transport
from winnow.reference_labels.routes import router as reference_labels_router
from winnow.review.routes import router as review_router
from winnow.rubric.routes import router as rubric_router
from winnow.selection.routes import router as selection_router
from winnow.sets.routes import router as sets_router
from winnow.tracking.routes import router as tracking_router
from winnow.triage.routes import router as triage_router
from winnow.visual.routes import router as visual_router
from winnow.voice.routes import router as voice_router


def create_app(settings: Settings | None = None, transport: Transport | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        ctx = build_context(settings or get_settings(), transport)
        ctx.jobs.fail_interrupted()
        app.state.context = ctx
        yield
        await ctx.runner.shutdown()
        ctx.db.close()

    app = FastAPI(title="Winnow", lifespan=lifespan)
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
