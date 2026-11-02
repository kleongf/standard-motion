from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from standard_motion.cli import main
from standard_motion.core.settings import Settings


def test_cli_ingest_adds_the_same_episodes_the_route_would(
    api: TestClient, settings: Settings, capsys: pytest.CaptureFixture[str]
):
    exit_code = main(["ingest", "droid_100", "0", "2"], settings=settings)

    assert exit_code == 0
    assert [e["id"] for e in api.get("/api/episodes").json()] == ["droid_100:0", "droid_100:2"]
    assert "2 done, 0 failed" in capsys.readouterr().out


def test_cli_exits_non_zero_when_an_episode_fails(settings: Settings):
    assert main(["ingest", "droid_100", "3"], settings=settings) == 1


def test_cli_writes_fixture_episodes(tmp_path: Path):
    assert main(["fixtures", str(tmp_path / "droid_100"), "--episodes", "1"]) == 0
    assert (tmp_path / "droid_100" / "main" / "meta" / "tasks.parquet").exists()
