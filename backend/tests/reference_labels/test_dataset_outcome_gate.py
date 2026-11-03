"""With `GROUND_TRUTH=dataset_outcome` no Reference label is given: the Dataset outcome is the
reference, so the blind gate is open and every Episode's outputs show."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from standard_motion.app import create_app
from standard_motion.core.settings import Settings
from tests.helpers import wait_for_job

UNLABELLED = "droid_100:2"  # a fixture Reject: two failed grasp attempts


@pytest.fixture
def open_api(settings: Settings) -> Iterator[TestClient]:
    with TestClient(
        create_app(settings.model_copy(update={"ground_truth": "dataset_outcome"}))
    ) as api:
        job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [0, 1, 2]})
        wait_for_job(api, job.json()["job_id"])
        yield api


def test_every_episode_has_its_triage_decision_without_a_reference_label(open_api: TestClient):
    rows = {r["episode_id"]: r for r in open_api.get("/api/triage").json()["rows"]}

    assert set(rows) == {"droid_100:0", "droid_100:1", UNLABELLED}
    assert open_api.get(f"/api/episodes/{UNLABELLED}/triage").json()["decision"] == "reject"


def test_the_episode_list_shows_each_dataset_outcome(open_api: TestClient):
    listed = {e["id"]: e for e in open_api.get("/api/episodes").json()}

    assert all(e["reference_labelled"] for e in listed.values())
    assert listed[UNLABELLED]["dataset_outcome"] is False  # the fixture marks it failed
    assert listed["droid_100:0"]["dataset_outcome"] is True
