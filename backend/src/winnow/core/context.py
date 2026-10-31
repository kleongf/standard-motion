"""App-level wiring shared by the API and the CLI: one database, the stores, the job runner."""

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from fastapi import Request

from winnow.audit.store import AuditStore
from winnow.baseline.service import baseline_step
from winnow.baseline.store import BaselineStore
from winnow.boxes.store import BoxStore
from winnow.calibration.store import CalibrationStore
from winnow.core.db import open_db
from winnow.core.settings import Settings
from winnow.episodes.droid101 import Droid101
from winnow.episodes.service import ingest_step
from winnow.episodes.sources import Source, sources_from
from winnow.episodes.store import EpisodeStore
from winnow.evaluation.store import TestRunLog
from winnow.interview.store import InterviewStore
from winnow.jobs.models import Step
from winnow.jobs.runner import JobRunner
from winnow.jobs.store import JobStore
from winnow.labels.store import LabelStore
from winnow.meta.client import MetaClient
from winnow.meta.costs import CostLog
from winnow.meta.limits import UNPACED_LIMITS, Limit
from winnow.meta.replay import ReplayTransport
from winnow.meta.transport import Transport
from winnow.reference_labels.store import ReferenceLabelStore
from winnow.rubric.draft_store import DraftStore
from winnow.rubric.seed import SEEDED
from winnow.rubric.store import RubricStore
from winnow.selection.service import select_step
from winnow.selection.store import SelectionStore
from winnow.sets.store import SetStore
from winnow.tracking.exterior import track_exterior_step
from winnow.tracking.store import TrackStore
from winnow.tracking.target import target_box_step
from winnow.tracking.target_store import TargetBoxStore
from winnow.tracking.wrist import track_wrist_step
from winnow.triage.reason_store import SparkReasonStore
from winnow.visual.steps import VisualSources, crop_step, visual_step
from winnow.visual.store import VisualStore


@dataclass(frozen=True)
class AppContext:
    settings: Settings
    db: sqlite3.Connection
    sources: dict[str, Source]
    episodes: EpisodeStore
    boxes: BoxStore
    baseline: BaselineStore
    selection: SelectionStore
    sets: SetStore
    tracks: TrackStore
    targets: TargetBoxStore
    rubrics: RubricStore
    drafts: DraftStore  # the Describe page's Rubric draft
    reference_labels: ReferenceLabelStore  # never read by scoring
    labels: LabelStore  # each overrides its Phrase's result, except an audit label
    audit: AuditStore  # the Audit sample drawn for each Rubric version
    calibrations: CalibrationStore  # the margin multiplier s each Rubric version is scored with
    interview: InterviewStore  # the Describe interview's answers on the draft
    test_runs: TestRunLog
    visual: VisualStore  # Spark's answers to visual Criteria
    reasons: SparkReasonStore  # Spark's Reasons, swapped in over the template ones
    jobs: JobStore
    runner: JobRunner
    meta: MetaClient | None  # None without a Meta API key: no step that calls Meta runs


def _meta(
    settings: Settings,
    db: sqlite3.Connection,
    transport: Transport | None,
    limits: Mapping[str, Limit],
) -> MetaClient | None:
    if transport is None and settings.meta_replay is not None:
        transport = ReplayTransport(settings.meta_replay)
    if transport is not None:  # tests script or replay the Meta API here
        costs = CostLog(settings.cost_log_path, settings.meta_budget_usd)
        return MetaClient(transport, db, costs, limits)
    if settings.model_api_key is None:
        return None
    return MetaClient.from_settings(settings, db)


def build_context(
    settings: Settings,
    transport: Transport | None = None,
    limits: Mapping[str, Limit] = UNPACED_LIMITS,
) -> AppContext:
    """A `transport` (or `meta_replay`) stands in for the Meta API and answers at once, so its
    calls skip the API's rate-limit spacing unless `limits` says otherwise, as when recording
    through the real API. The real API's own client always uses `DEFAULT_LIMITS`."""
    db = open_db(settings.db_path)
    sources = sources_from(settings)
    episodes = EpisodeStore(db, settings.data_dir)
    boxes = BoxStore(db)
    baseline = BaselineStore(db)
    selection = SelectionStore(db)
    sets = SetStore(db)
    tracks = TrackStore(db)
    targets = TargetBoxStore(db)
    rubrics = RubricStore(db, SEEDED)
    drafts = DraftStore(db)
    reference_labels = ReferenceLabelStore(db)
    labels = LabelStore(db)
    audit = AuditStore(db)
    calibrations = CalibrationStore(db)
    interview = InterviewStore(db)
    test_runs = TestRunLog(db)
    visual = VisualStore(db)
    reasons = SparkReasonStore(db)
    jobs = JobStore(db)
    meta = _meta(settings, db, transport, limits)
    visual_sources = VisualSources(rubrics, episodes, boxes, tracks, targets, visual)
    steps: dict[str, Step] = {
        "ingest": ingest_step(episodes, sources),
        "crop": crop_step(visual_sources),
    }
    droid101 = sources.get("droid_1.0.1")
    if meta is not None:
        steps["baseline"] = baseline_step(meta, baseline, episodes)
        steps["track_wrist"] = track_wrist_step(meta, tracks, episodes)
        steps["track_exterior"] = track_exterior_step(meta, tracks, boxes, episodes)
        steps["target_box"] = target_box_step(meta, targets, boxes, episodes)
        steps["visual"] = visual_step(meta, visual_sources)
        if isinstance(droid101, Droid101):
            steps["select"] = select_step(meta, selection, droid101, settings.data_dir)
    runner = JobRunner(jobs, steps, concurrency=settings.ingest_concurrency)
    ctx = AppContext(
        settings,
        db,
        sources,
        episodes,
        boxes,
        baseline,
        selection,
        sets,
        tracks,
        targets,
        rubrics,
        drafts,
        reference_labels,
        labels,
        audit,
        calibrations,
        interview,
        test_runs,
        visual,
        reasons,
        jobs,
        runner,
        meta,
    )
    # These steps score Episodes through the context, so they're added once that exists; the
    # runner reads `steps` when an item runs.
    from winnow.export.service import export_step

    steps["export"] = export_step(ctx)
    if meta is not None:
        from winnow.triage.reason_steps import reason_step

        steps["reason"] = reason_step(meta, ctx)
    return ctx


def get_context(request: Request) -> AppContext:
    """FastAPI dependency: the context `create_app`'s lifespan built."""
    return cast(AppContext, request.app.state.context)
