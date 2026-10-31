"""Shared fixtures: a synthetic droid_100 source and the app running against a fresh data dir."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.helpers import wait_for_job
from tests.record_meta import E2E_EPISODES
from tests.tracking.scripted_sam import ScriptedSam
from tests.visual.scripted import ScriptedVisual
from winnow.app import create_app
from winnow.core.settings import Settings
from winnow.episodes.fixtures import write_fixture_source
from winnow.episodes.fixtures_droid101 import write_droid101_fixture

# Episode 3 of the fixture source has unreadable video; in Episode 4 the gripper never closes.
CORRUPT_EPISODE = 3
OPEN_GRIPPER_EPISODE = 4


@pytest.fixture(scope="session")
def droid100_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("droid_100")
    return write_fixture_source(
        root, episodes=5, corrupt=(CORRUPT_EPISODE,), open_gripper=(OPEN_GRIPPER_EPISODE,)
    )


@pytest.fixture(scope="session")
def e2e_droid100_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """e2e's fixture source, which every recorded reply was recorded against. Replay modules
    override `droid100_root` with it."""
    return write_fixture_source(tmp_path_factory.mktemp("e2e_droid_100"), episodes=E2E_EPISODES)


@pytest.fixture(scope="session")
def droid101_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_droid101_fixture(tmp_path_factory.mktemp("droid_1.0.1"))


@pytest.fixture
def settings(tmp_path: Path, droid100_root: Path, droid101_root: Path) -> Settings:
    return Settings(
        model_api_key=None,
        data_dir=tmp_path / "data",
        droid100_root=droid100_root,
        droid101_root=droid101_root,
    )


@pytest.fixture
def api(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.fixture
def sam() -> ScriptedSam:
    return ScriptedSam()


@pytest.fixture
def scripted_api(settings: Settings, sam: ScriptedSam) -> Iterator[TestClient]:
    """The app with a scripted SAM and fixture Episodes 0-2 ingested."""
    with TestClient(create_app(settings, transport=sam)) as client:
        job = client.post(
            "/api/episodes/ingest", json={"source": "droid_100", "indices": [0, 1, 2]}
        )
        wait_for_job(client, job.json()["job_id"])
        yield client


@pytest.fixture
def visual_spark() -> ScriptedVisual:
    return ScriptedVisual()


@pytest.fixture
def asked_api(settings: Settings, visual_spark: ScriptedVisual) -> Iterator[TestClient]:
    """The app with a scripted Meta API, so `tests.helpers.ask_visual` can answer the seeded
    Rubric's placement question (pass on every sample, unless scripted otherwise)."""
    with TestClient(create_app(settings, transport=visual_spark)) as client:
        yield client
