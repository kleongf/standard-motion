"""The label store: a human's pass or fail on one Phrase of one Episode overrides that Phrase's
result, and the Triage decision recomputes on the next read."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import ask_visual, reference_label, track_cleanly, wait_for_job
from winnow.baseline.prompts import FROZEN

FIRST_TRY, NEVER_DROPS, _, NO_PAUSES = FROZEN.phrases
NEAR_THRESHOLD = "droid_100:1"  # Needs review: its release height (4.4 cm) is its only unsure


@pytest.fixture
def ingested(asked_api: TestClient) -> TestClient:
    api = asked_api  # Spark sees every Episode's object placed on its target
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [0, 1]})
    wait_for_job(api, job.json()["job_id"])
    ask_visual(api)
    track_cleanly(api, NEAR_THRESHOLD)  # so its tracked Criteria pass and leave release height
    reference_label(api, NEAR_THRESHOLD)
    return api


def label(api: TestClient, episode_id: str, phrase: str, value: str, source: str = "review"):
    return api.post(
        f"/api/episodes/{episode_id}/labels",
        json={"phrase": phrase, "value": value, "source": source},
    )


def triage(api: TestClient, episode_id: str) -> Any:
    return api.get(f"/api/episodes/{episode_id}/triage").json()


def test_labelling_the_only_unsure_phrase_pass_keeps_the_episode(ingested: TestClient):
    assert triage(ingested, NEAR_THRESHOLD)["decision"] == "needs_review"

    saved = label(ingested, NEAR_THRESHOLD, NEVER_DROPS, "pass")

    assert saved.status_code == 201, saved.text
    stored = saved.json()
    assert (stored["episode_id"], stored["phrase"], stored["value"], stored["source"]) == (
        NEAR_THRESHOLD,
        NEVER_DROPS,
        "pass",
        "review",
    )
    assert stored["rubric_version"] == 1 and stored["labelled_at"]
    after = triage(ingested, NEAR_THRESHOLD)
    assert after["decision"] == "keep"


def test_labelling_it_fail_rejects_with_a_reason_naming_the_phrase_and_source(
    ingested: TestClient,
):
    label(ingested, NEAR_THRESHOLD, NEVER_DROPS, "fail")

    after = triage(ingested, NEAR_THRESHOLD)
    assert after["decision"] == "reject"
    assert "".join(s["text"] for s in after["reason"]) == (
        f'Rejected: "{NEVER_DROPS}" was marked fail in review.'
    )
    rows = {r["episode_id"]: r for r in ingested.get("/api/triage").json()["rows"]}
    assert rows[NEAR_THRESHOLD]["decision"] == "reject"  # the Episodes table agrees


def test_a_new_answer_supersedes_the_last_and_both_stay_in_history(ingested: TestClient):
    label(ingested, NEAR_THRESHOLD, NEVER_DROPS, "fail", source="interview")
    label(ingested, NEAR_THRESHOLD, NEVER_DROPS, "pass")

    assert triage(ingested, NEAR_THRESHOLD)["decision"] == "keep"
    history = ingested.get(f"/api/episodes/{NEAR_THRESHOLD}/labels").json()
    assert [(h["source"], h["value"]) for h in history] == [
        ("interview", "fail"),
        ("review", "pass"),
    ]


def test_an_episode_without_a_reference_label_cant_be_labelled(ingested: TestClient):
    assert label(ingested, "droid_100:0", NEVER_DROPS, "pass").status_code == 403


def test_a_label_must_name_a_phrase_of_the_rubric(ingested: TestClient):
    response = label(ingested, NEAR_THRESHOLD, "picks it up gently", "pass")

    assert response.status_code == 422
    assert triage(ingested, NEAR_THRESHOLD)["decision"] == "needs_review"
