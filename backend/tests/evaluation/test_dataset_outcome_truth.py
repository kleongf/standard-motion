"""With `GROUND_TRUTH=dataset_outcome` the report scores every set Episode with a Dataset outcome
against it, and leaves out what needs a Reference label's failing Phrase and time."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from standard_motion.app import create_app
from standard_motion.cli import main
from standard_motion.core.settings import Settings
from tests.evaluation.test_evaluation_api import EPISODES, run, spark_alone, typed
from tests.helpers import ask_visual, track_cleanly, wait_for_job
from tests.visual.scripted import ScriptedVisual


@pytest.fixture
def outcome_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"ground_truth": "dataset_outcome"})


@pytest.fixture
def outcome_set(outcome_settings: Settings, visual_spark: ScriptedVisual) -> Iterator[TestClient]:
    with TestClient(create_app(outcome_settings, transport=visual_spark)) as api:
        indices = [int(id_.split(":")[1]) for id_ in EPISODES]
        job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": indices})
        wait_for_job(api, job.json()["job_id"])
        track_cleanly(api, "droid_100:0")
        ask_visual(api)
        api.post("/api/sets/test/episodes", json={"episode_ids": EPISODES})
        spark_alone(api, "droid_100:0", "keep", "keep", "reject")
        spark_alone(api, "droid_100:2", "reject", "reject", "keep")
        yield api


def test_every_set_episode_is_scored_against_its_dataset_outcome(outcome_set: TestClient):
    report = run(outcome_set, "test")
    outcomes = {e["id"]: e["dataset_outcome"] for e in outcome_set.get("/api/episodes").json()}

    assert report["ground_truth"] == "dataset_outcome"
    assert (report["episodes"], report["labelled"]) == (4, 4)
    assert report["description_failures"] == sum(outcomes[id_] is False for id_ in EPISODES)
    row = typed(report).comparison.rows[0]
    assert (row.system, row.keeps + row.rejects + row.undecided) == ("standard_motion", 4)


def test_what_needs_a_reference_label_is_left_out(outcome_set: TestClient):
    report = run(outcome_set, "test")

    assert report["right_reason"] is None
    assert report["phrase_failures"] is None
    assert report["dataset_outcome"] is None
    assert report["failbench"] is not None
    assert all(row.right_reason is None for row in typed(report).ablation)


def test_the_cli_names_the_ground_truth(
    outcome_set: TestClient, outcome_settings: Settings, capsys: pytest.CaptureFixture[str]
):
    assert main(["eval", "dev"], outcome_settings) == 0
    printed = capsys.readouterr().out

    assert "Ground truth: the Dataset outcome" in printed
    assert "Right reason and failures per Phrase need Reference labels: not measured." in printed
