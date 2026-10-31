"""e2e's dry run under the replay transport: compiling `tests.record_dry_run`'s Description asks
its visual Criterion of e2e's Dev set Episode from the scripted answers, with the real `meta/`
code underneath, so the Describe page shows its pass rate without a Run."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import reference_label, wait_for_job
from tests.record_dry_run import DRY_RUN_ANSWERS, IN_BOWL, PLACED
from tests.record_meta import E2E_DEV_SET, RECORDINGS
from winnow.app import create_app
from winnow.core.settings import Settings
from winnow.meta.replay import ReplayTransport
from winnow.visual.service import DRY_RUN

DEV = [f"droid_100:{i}" for i in E2E_DEV_SET]


@pytest.fixture(scope="module")
def droid100_root(e2e_droid100_root: Path) -> Path:
    """e2e's fixture source, which the scripted replies were recorded against."""
    return e2e_droid100_root


@pytest.fixture
def replay_api(settings: Settings, tmp_path: Path) -> Iterator[TestClient]:
    replies = tmp_path / "replies.jsonl"
    replies.write_text(RECORDINGS.read_text() + DRY_RUN_ANSWERS.read_text())
    with TestClient(create_app(settings, transport=ReplayTransport(replies))) as client:
        body = {"source": "droid_100", "indices": list(E2E_DEV_SET)}
        wait_for_job(client, client.post("/api/episodes/ingest", json=body).json()["job_id"])
        client.post("/api/sets/dev/episodes", json={"episode_ids": DEV})
        for episode in DEV:
            reference_label(client, episode)
        yield client


def dry_run(api: TestClient) -> Any:
    job = api.get("/api/jobs/latest", params={"kind": DRY_RUN}).json()
    assert job is not None, "no dry run was queued"
    return wait_for_job(api, job["id"])


def test_the_scripted_compile_asks_its_visual_criterion_from_the_scripted_answers(
    replay_api: TestClient,
):
    compiled = replay_api.post("/api/rubric/draft/compile", json={"description": PLACED})
    assert compiled.status_code == 200, compiled.text
    [placed] = compiled.json()["criteria"]
    assert (placed["phrase"], placed["kind"]) == (IN_BOWL, "visual")

    job = dry_run(replay_api)

    assert (job["done"], job["failed"]) == (2, 0)
    preview = replay_api.post("/api/rubric/draft/preview", json={}).json()
    [found] = preview["criteria"]
    assert (found["passing"], found["failing"], found["unsure"]) == (1, 0, 0)
