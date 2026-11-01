"""The frozen Description compiled by Spark itself, replayed from its recorded reply."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tests.helpers import wait_for_job
from tests.record_meta import RECORDINGS
from winnow.app import create_app
from winnow.baseline.prompts import FROZEN
from winnow.core.settings import Settings

FIRST_TRY, NEVER_DROPS, PLACES, NO_PAUSES = FROZEN.phrases


@pytest.fixture
def replay_api(settings: Settings) -> Iterator[TestClient]:
    replayed = settings.model_copy(update={"meta_replay": RECORDINGS})
    with TestClient(create_app(replayed)) as client:
        yield client


def test_the_frozen_description_compiles_to_the_expected_criteria(replay_api: TestClient):
    # The recording compiled against e2e's Dev set, whose Episode has Episode 0's robot data.
    job = replay_api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [0]})
    wait_for_job(replay_api, job.json()["job_id"])
    replay_api.post("/api/sets/dev/episodes", json={"episode_ids": ["droid_100:0"]})

    response = replay_api.post("/api/rubric/draft/compile", json={"description": FROZEN.text})

    assert response.status_code == 200, response.text
    draft = response.json()
    assert [(p["text"], p["status"]) for p in draft["phrases"]] == [
        ("Expert pick-and-place:", "context"),
        (FIRST_TRY, "checked"),
        (NEVER_DROPS, "checked"),
        (PLACES, "checked"),
        (NO_PAUSES, "checked"),
    ]
    by_phrase = {c["phrase"]: draft["english"][c["id"]] for c in draft["criteria"]}
    assert by_phrase == {
        FIRST_TRY: "Grasp attempts, up to and including the grasp, ≤ 1",
        NEVER_DROPS: "Time the object is out of the closed gripper (wrist view), while holding, "
        "≤ 0.2 s",
        PLACES: "Share of the object's final box inside the target box ≥ 0.50",
        NO_PAUSES: "Longest stretch with the arm under 0.01 m/s < 1 s",
    }
    pauses = next(c for c in draft["criteria"] if c["phrase"] == NO_PAUSES)
    assert pauses["assumptions"]  # Spark chose the 1 s
    assert all(p["reason"] for p in draft["phrases"] if p["status"] != "checked")
    assert draft["uncovered"] == []  # every meaningful word is in a Phrase
    assert draft["rejected"] == []
