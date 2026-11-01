"""Until an Episode has a first-pass Reference label, its Winnow and Spark-alone outputs stay out
of every API response the app reads, so labels are given blind."""

import pytest
from fastapi.testclient import TestClient

from tests.helpers import reference_label, wait_for_job

UNLABELLED = "droid_100:2"  # a fixture Reject: two failed grasp attempts
LABELLED = "droid_100:0"


@pytest.fixture
def ingested(api: TestClient) -> TestClient:
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [0, 1, 2]})
    wait_for_job(api, job.json()["job_id"])
    reference_label(api, LABELLED)
    return api


def triage_rows(api: TestClient) -> dict[str, dict[str, object]]:
    return {r["episode_id"]: r for r in api.get("/api/triage").json()["rows"]}


def test_an_unlabelled_episode_has_no_triage_decision_or_reason_in_the_list(
    ingested: TestClient,
):
    assert set(triage_rows(ingested)) == {LABELLED}


def test_an_unlabelled_episodes_criterion_results_are_withheld(ingested: TestClient):
    hidden = ingested.get(f"/api/episodes/{UNLABELLED}/triage")

    assert hidden.status_code == 403
    assert hidden.json() == {
        "detail": f"{UNLABELLED} has no Reference label yet, so its outputs stay hidden"
    }


def test_labelling_an_episode_reveals_its_outputs(ingested: TestClient):
    reference_label(ingested, UNLABELLED)

    assert triage_rows(ingested)[UNLABELLED]["decision"] == "reject"
    triage = ingested.get(f"/api/episodes/{UNLABELLED}/triage").json()
    assert triage["decision"] == "reject"
    # Grasp attempts fail; like Episode 42 it also releases high, an unconfirmed fail. Spark
    # hasn't been asked whether it was placed.
    statuses = {r["criterion_id"]: r["status"] for r in triage["criteria"]}
    measured = ("grasp-attempts", "release-height", "longest-pause", "placed-on-target")
    assert [statuses[id_] for id_ in measured] == ["fail", "fail", "pass", "unsure"]


def test_the_episode_list_says_which_episodes_await_a_reference_label(ingested: TestClient):
    listed = {e["id"]: e["reference_labelled"] for e in ingested.get("/api/episodes").json()}

    assert listed == {LABELLED: True, "droid_100:1": False, UNLABELLED: False}


def test_an_unknown_episode_is_still_not_found(ingested: TestClient):
    assert ingested.get("/api/episodes/droid_100:9/triage").status_code == 404
