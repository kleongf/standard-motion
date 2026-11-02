"""The Review queue: Needs review Episodes, strictly least confident first, each with only the
Phrases Standard Motion couldn't decide. An answered Episode that is decided leaves it."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from standard_motion.baseline.prompts import FROZEN
from standard_motion.rubric.models import Rubric
from tests.conftest import OPEN_GRIPPER_EPISODE
from tests.helpers import app_context, ask_visual, reference_label, track_cleanly, wait_for_job

_, NEVER_DROPS, _, _ = FROZEN.phrases
INDICES = [0, 1, 2, OPEN_GRIPPER_EPISODE]


@pytest.fixture
def ingested(asked_api: TestClient) -> TestClient:
    api = asked_api  # Spark sees every Episode's object placed on its target
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": INDICES})
    wait_for_job(api, job.json()["job_id"])
    ask_visual(api)
    for index in INDICES:
        track_cleanly(api, f"droid_100:{index}")  # tracked Criteria pass; release height decides
        reference_label(api, f"droid_100:{index}")
    return api


def queue(api: TestClient) -> Any:
    return api.get("/api/review").json()


def test_the_queue_holds_needs_review_episodes_with_only_their_unsure_phrases(
    ingested: TestClient,
):
    listed = queue(ingested)

    assert listed["rubric_version"] == 1
    (item,) = listed["items"]
    assert item["episode_id"] == "droid_100:1"
    assert 0.5 < item["confidence"] < 0.95
    assert item["unsure"] == [
        {"phrase": NEVER_DROPS, "signals": ["near threshold (4.4 cm against ≤ 5 cm)"]}
    ]
    assert listed["reviewed"] == 0


def test_an_answered_episode_that_is_decided_leaves_the_queue(ingested: TestClient):
    ingested.post(
        "/api/episodes/droid_100:1/labels",
        json={"phrase": NEVER_DROPS, "value": "pass", "source": "review"},
    )

    listed = queue(ingested)

    assert listed["items"] == []
    assert listed["reviewed"] == 1


def test_the_queue_is_ordered_least_confident_first(ingested: TestClient):
    # Only the release height decides, with a 3 cm margin: Episode 2 (6.5 cm, an inconclusive
    # fail held at p 0.5) and 4 (no grasp, so no release) tie at 0.5, ahead of 1 (4.4 cm).
    rubrics = app_context(ingested).rubrics
    wider = rubrics.latest().rubric.model_copy(deep=True)
    wider.criteria = [c for c in wider.criteria if c.id == "release-height"]
    wider.criteria[0].margin = 0.03
    rubrics.add(Rubric.model_validate(wider.model_dump()))

    items = queue(ingested)["items"]

    assert [i["episode_id"] for i in items] == ["droid_100:2", "droid_100:4", "droid_100:1"]
    assert [i["confidence"] for i in items] == pytest.approx([0.5, 0.5, 0.65], abs=0.01)


def test_a_review_label_on_a_phrase_the_rubric_no_longer_has_is_not_counted(
    ingested: TestClient,
):
    ingested.post(
        "/api/episodes/droid_100:1/labels",
        json={"phrase": NEVER_DROPS, "value": "pass", "source": "review"},
    )
    rubrics = app_context(ingested).rubrics
    edited = rubrics.latest().rubric.model_copy(deep=True)
    edited.phrases = [p for p in edited.phrases if p != NEVER_DROPS]
    edited.criteria = [c for c in edited.criteria if c.phrase != NEVER_DROPS]
    rubrics.add(Rubric.model_validate(edited.model_dump()))

    listed = queue(ingested)

    assert listed["items"] == []  # decided without the Phrase, not by the detached label
    assert listed["reviewed"] == 0


def test_a_test_set_episode_never_enters_the_queue(ingested: TestClient):
    app_context(ingested).sets.add("test", ["droid_100:1"])

    listed = queue(ingested)

    assert listed["items"] == []  # held out, so no review label is ever asked of it
