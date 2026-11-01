"""The report over fixture Episodes ingested through the replay transport, with the real `meta/`
code underneath: the source ablation and the Spark-alone disagreements re-score what is stored,
so neither makes a Meta call, and cost per 1,000 Episodes is read from the cost log ingest
wrote."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.evaluation.test_evaluation_api import reference_label
from tests.helpers import ask_visual, wait_for_job
from tests.record_meta import RECORDINGS
from tests.record_visual import VISUAL_ANSWERS
from tests.rubric.replay import CountingReplay
from winnow.app import create_app
from winnow.baseline.prompts import FROZEN
from winnow.core.settings import Settings
from winnow.evaluation.models import EvaluationReport
from winnow.evaluation.protocol_models import Disagreement
from winnow.meta.costs import CostLog
from winnow.meta.replay import ReplayTransport

FIRST_TRY = FROZEN.phrases[0]
# Fixture Episode 0 grasps cleanly, 2 is rejected after failed grasps, and 10's scripted visual
# samples split. Unboxed, 0 and 10 need review; Spark alone's recorded answers reject all three.
EPISODES = ["droid_100:0", "droid_100:2", "droid_100:10"]


@pytest.fixture(scope="module")
def droid100_root(e2e_droid100_root: Path) -> Path:
    """e2e's fixture source, which the replies were recorded against."""
    return e2e_droid100_root


@pytest.fixture
def transport(tmp_path: Path) -> CountingReplay:
    replies = tmp_path / "replies.jsonl"
    replies.write_text(RECORDINGS.read_text() + VISUAL_ANSWERS.read_text())
    return CountingReplay(ReplayTransport(replies))


@pytest.fixture
def labelled(settings: Settings, transport: CountingReplay) -> Iterator[TestClient]:
    with TestClient(create_app(settings, transport=transport)) as client:
        job = client.post(
            "/api/episodes/ingest", json={"source": "droid_100", "indices": [0, 2, 10]}
        )
        wait_for_job(client, job.json()["job_id"])
        ask_visual(client)
        client.post("/api/sets/test/episodes", json={"episode_ids": EPISODES})
        reference_label(client, "droid_100:0")
        reference_label(client, "droid_100:2", FIRST_TRY, interval=(0.0, 2.9))
        reference_label(client, "droid_100:2", FIRST_TRY, interval=(0.0, 2.4), relabel=True)
        reference_label(client, "droid_100:10")
        yield client


def test_the_ablation_and_the_disagreements_make_zero_meta_calls(
    labelled: TestClient, transport: CountingReplay, settings: Settings
):
    calls, costs = transport.calls, settings.cost_log_path.read_text()
    assert calls > 0  # ingest and the visual question went through it

    report = labelled.post("/api/evaluation/runs", json={"set_name": "test"})
    listed = labelled.get("/api/evaluation/disagreements")

    assert (report.status_code, listed.status_code) == (200, 200)
    assert (transport.calls, settings.cost_log_path.read_text()) == (calls, costs)
    ablation = EvaluationReport.model_validate(report.json()).ablation
    assert [(r.mask, r.criteria, r.of) for r in ablation] == [
        ("robot_data", 3, 7),
        ("robot_data_sam", 6, 7),
        ("robot_data_visual", 4, 7),
        ("all", 7, 7),
    ]
    # Every row rejects Episode 2 on its grasp attempts, inside the labelled interval.
    assert all((r.false_keeps.count, r.false_keeps.of) == (0, 1) for r in ablation)
    assert all(
        r.right_reason and (r.right_reason.count, r.right_reason.of) == (1, 1) for r in ablation
    )


def test_cost_per_1000_episodes_is_extrapolated_from_what_ingest_logged(
    labelled: TestClient, settings: Settings
):
    logged = CostLog(settings.cost_log_path, settings.meta_budget_usd).entries()
    wrist = sum(e.usd for e in logged if e.purpose.startswith("track_wrist:"))
    visual = sum(e.usd for e in logged if e.purpose.startswith("visual:"))
    baseline = sum(e.usd for e in logged if e.purpose.startswith("baseline:"))

    cost = EvaluationReport.model_validate(
        labelled.post("/api/evaluation/runs", json={"set_name": "test"}).json()
    ).cost

    assert wrist > 0 and visual > 0 and baseline > 0
    assert cost.episodes == 3
    assert cost.winnow_usd == pytest.approx(wrist + visual)
    assert cost.winnow_per_1000_usd == pytest.approx((wrist + visual) / 3 * 1000)
    assert cost.spark_alone_usd == pytest.approx(baseline)
    assert [s.step for s in cost.steps] == ["track_wrist", "visual", "baseline"]


def test_each_disagreement_names_both_decisions_and_the_reference_label(labelled: TestClient):
    rows = [
        Disagreement.model_validate(r) for r in labelled.get("/api/evaluation/disagreements").json()
    ]

    # Episode 2: both reject, so it isn't listed.
    assert [(r.episode_id, r.winnow, r.spark_alone, r.set_name) for r in rows] == [
        ("droid_100:0", "needs_review", "reject", "test"),
        ("droid_100:10", "needs_review", "reject", "test"),
    ]
    assert all(r.spark_alone_reason and r.winnow_reason for r in rows)
    assert all(r.failed_phrases == [] for r in rows)
