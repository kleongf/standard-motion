"""The seeded placement question under the replay transport, scored from the answers e2e replays
(written by `tests.record_visual`), with the real `meta/` code underneath."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.helpers import ask_visual, reference_label, wait_for_job
from tests.record_meta import RECORDINGS
from tests.record_visual import VISUAL_ANSWERS
from tests.rubric.replay import CountingReplay
from winnow.app import create_app
from winnow.core.settings import Settings
from winnow.meta.replay import ReplayTransport

SPLIT = 10  # the Episode `tests.record_visual` scripts to split 2-1


@pytest.fixture(scope="module")
def droid100_root(e2e_droid100_root: Path) -> Path:
    """e2e's fixture source, which the scripted answers were recorded against."""
    return e2e_droid100_root


@pytest.fixture
def replay(tmp_path: Path) -> CountingReplay:
    replies = tmp_path / "replies.jsonl"
    replies.write_text(RECORDINGS.read_text() + VISUAL_ANSWERS.read_text())
    return CountingReplay(ReplayTransport(replies))


@pytest.fixture
def replay_api(settings: Settings, replay: CountingReplay) -> Iterator[TestClient]:
    with TestClient(create_app(settings, transport=replay)) as client:
        job = client.post(
            "/api/episodes/ingest", json={"source": "droid_100", "indices": [0, SPLIT]}
        )
        wait_for_job(client, job.json()["job_id"])
        yield client


def placement(api: TestClient, episode_id: str) -> dict[str, object]:
    reference_label(api, episode_id)
    triage = api.get(f"/api/episodes/{episode_id}/triage").json()
    return next(c for c in triage["criteria"] if c["kind"] == "visual")


def test_a_visual_criterion_scores_fixture_episodes_from_recorded_answers(
    replay_api: TestClient,
):
    job = ask_visual(replay_api)

    assert job["failed"] == 0
    kept = placement(replay_api, "droid_100:0")
    assert (kept["status"], kept["measurement"]) == ("pass", "3 pass")
    split = placement(replay_api, f"droid_100:{SPLIT}")
    assert (split["status"], split["uncertainty"]) == ("unsure", "samples split")


def test_asking_again_is_all_cache_hits(replay_api: TestClient, replay: CountingReplay):
    # Only the visual question's calls count: asking also queues Spark's Reasons, which run
    # alongside and aren't recorded here, so they fail, are never cached, and call every time.
    ask_visual(replay_api)
    before = replay.formats.count("visual")

    again = ask_visual(replay_api)

    assert again["failed"] == 0
    assert before > 0
    assert replay.formats.count("visual") == before
