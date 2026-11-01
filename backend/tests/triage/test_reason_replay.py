"""e2e's Spark Reason under the replay transport, from the reply `tests.record_reason` wrote, with
the real `meta/` code underneath."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.helpers import reference_label, wait_for_job
from tests.record_meta import RECORDINGS
from tests.record_reason import REASON_ANSWERS, REASON_EPISODE
from winnow.app import create_app
from winnow.core.settings import Settings
from winnow.meta.replay import ReplayTransport

EPISODE = f"droid_100:{REASON_EPISODE}"


@pytest.fixture(scope="module")
def droid100_root(e2e_droid100_root: Path) -> Path:
    """e2e's fixture source, which the Reason reply was recorded against."""
    return e2e_droid100_root


@pytest.fixture
def replay_api(settings: Settings, tmp_path: Path) -> Iterator[TestClient]:
    replies = tmp_path / "replies.jsonl"
    replies.write_text(RECORDINGS.read_text() + REASON_ANSWERS.read_text())
    with TestClient(create_app(settings, transport=ReplayTransport(replies))) as client:
        body = {"source": "droid_100", "indices": [REASON_EPISODE]}
        wait_for_job(client, client.post("/api/episodes/ingest", json=body).json()["job_id"])
        reference_label(client, EPISODE)
        yield client


def test_the_scripted_reason_replays_and_replaces_the_template(replay_api: TestClient):
    started = replay_api.post("/api/reasons")
    job = wait_for_job(replay_api, started.json()["job_id"])

    assert (job["done"], job["failed"]) == (1, 0)
    triage = replay_api.get(f"/api/episodes/{EPISODE}/triage").json()
    assert triage["reason_source"] == "spark"
    assert "".join(s["text"] for s in triage["reason"]) == (
        "The gripper closed on nothing at 0.9 s and again at 1.3 s, only holding the object "
        "from 1.8 s, so it wasn't grasped on the first try."
    )
    assert [s["t"] for s in triage["reason"] if s["t"] is not None] == [
        m["t"] for m in triage["criteria"][0]["moments"]
    ]
