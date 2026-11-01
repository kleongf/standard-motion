"""Freezing a set that breaks the protocol is a warning, then a confirmed or forced freeze."""

import io

import pytest
from fastapi.testclient import TestClient

from tests.helpers import wait_for_job
from winnow.cli import main
from winnow.core.settings import Settings
from winnow.sets import protocol
from winnow.sets.models import EpisodeSet, SetName
from winnow.sets.protocol import SEEN_EPISODES, TEST_SET_SIZE, freeze_warnings


@pytest.fixture
def ingested(api: TestClient) -> TestClient:
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [0, 1, 2]})
    wait_for_job(api, job.json()["job_id"])
    return api


def add(api: TestClient, name: str, *ids: str):
    return api.post(f"/api/sets/{name}/episodes", json={"episode_ids": list(ids)})


def frozen_at(api: TestClient, name: str) -> str | None:
    return {s["name"]: s for s in api.get("/api/sets").json()}[name]["frozen_at"]


def episode_set(name: SetName, size: int, ids: tuple[str, ...] = ()) -> EpisodeSet:
    members = list(ids) or [f"droid_100:{1000 + i}" for i in range(size)]  # none of them seen
    return EpisodeSet(name=name, size=len(members), frozen_at=None, episode_ids=members)


def test_the_test_set_must_hold_exactly_100_episodes():
    assert freeze_warnings(episode_set("test", TEST_SET_SIZE)) == []
    for size in (TEST_SET_SIZE - 1, TEST_SET_SIZE + 1):
        (warning,) = freeze_warnings(episode_set("test", size))
        assert "Test set" in warning and "exactly 100" in warning and str(size) in warning


def test_the_test_set_must_hold_none_of_the_episodes_already_seen():
    unseen = ("droid_100:1000", "droid_100:1001")
    assert freeze_warnings(episode_set("test", 0, unseen)) != []  # only the size is wrong
    assert all("seen" not in w for w in freeze_warnings(episode_set("test", 0, unseen)))

    members = (*unseen, SEEN_EPISODES[0], SEEN_EPISODES[6])
    warnings = freeze_warnings(episode_set("test", 0, members))

    (seen,) = [w for w in warnings if "seen" in w]
    assert "Test set" in seen and SEEN_EPISODES[0] in seen and SEEN_EPISODES[6] in seen
    assert SEEN_EPISODES[1] not in seen and "droid_100:1000" not in seen

    full = tuple(f"droid_100:{1000 + i}" for i in range(TEST_SET_SIZE - 1))
    (only,) = freeze_warnings(episode_set("test", 0, (*full, SEEN_EPISODES[0])))
    assert "seen" in only  # right size, so the seen Episode is the only warning


def test_the_dev_set_must_hold_every_episode_already_seen():
    assert freeze_warnings(episode_set("dev", 0, SEEN_EPISODES)) == []
    assert freeze_warnings(episode_set("dev", 0, (*SEEN_EPISODES, "droid_100:7"))) == []

    (warning,) = freeze_warnings(episode_set("dev", 0, SEEN_EPISODES[1:]))

    assert "Dev set" in warning and SEEN_EPISODES[0] in warning
    assert SEEN_EPISODES[1] not in warning


def test_the_seen_episodes_are_the_hand_inspected_ones():
    assert set(SEEN_EPISODES) == {
        *(f"droid_100:{i}" for i in (3, 16, 42, 48, 49)),
        *(f"droid_1.0.1:{i}" for i in (1, 9, 17)),
    }


def test_an_unforced_freeze_returns_the_warnings_and_freezes_nothing(ingested: TestClient):
    add(ingested, "test", "droid_100:0")

    response = ingested.post("/api/sets/test/freeze")

    assert response.status_code == 409
    body = response.json()
    assert body["warnings"] == freeze_warnings(episode_set("test", 1, ("droid_100:0",)))
    assert body["detail"] == body["warnings"][0]
    assert frozen_at(ingested, "test") is None
    assert add(ingested, "test", "droid_100:1").status_code == 200  # still open


def test_forcing_freezes_despite_the_warnings(ingested: TestClient):
    add(ingested, "dev", "droid_100:0")

    refused = ingested.post("/api/sets/dev/freeze", json={"force": False})
    forced = ingested.post("/api/sets/dev/freeze", json={"force": True})

    assert refused.status_code == 409
    assert forced.status_code == 200 and forced.json()["frozen_at"] == frozen_at(ingested, "dev")


def test_a_set_that_keeps_the_protocol_freezes_without_force(
    ingested: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(protocol, "SEEN_EPISODES", ("droid_100:0", "droid_100:1"))
    monkeypatch.setattr(protocol, "TEST_SET_SIZE", 1)
    add(ingested, "dev", "droid_100:0", "droid_100:1")
    add(ingested, "test", "droid_100:2")

    assert ingested.post("/api/sets/dev/freeze").status_code == 200
    assert ingested.post("/api/sets/test/freeze").status_code == 200


def test_an_empty_set_is_still_refused_even_when_forced(api: TestClient):
    forced = api.post("/api/sets/test/freeze", json={"force": True})

    assert forced.status_code == 422 and "empty" in forced.json()["detail"]


def test_the_cli_freezes_after_a_yes_and_leaves_the_set_open_after_a_no(
    ingested: TestClient,
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
):
    main(["sets", "add", "test", "droid_100:0"], settings=settings)

    monkeypatch.setattr("sys.stdin", io.StringIO("n\n"))
    declined = main(["sets", "freeze", "test"], settings=settings)

    err = capsys.readouterr().err
    assert declined == 1 and "exactly 100" in err and "Freeze anyway?" in err
    assert frozen_at(ingested, "test") is None

    monkeypatch.setattr("sys.stdin", io.StringIO(""))  # no answer is a no
    assert main(["sets", "freeze", "test"], settings=settings) == 1
    assert frozen_at(ingested, "test") is None

    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))
    assert main(["sets", "freeze", "test"], settings=settings) == 0
    assert frozen_at(ingested, "test") is not None


def test_the_cli_yes_flag_skips_the_question(
    ingested: TestClient, settings: Settings, capsys: pytest.CaptureFixture[str]
):
    main(["sets", "add", "dev", "droid_100:0"], settings=settings)

    assert main(["sets", "freeze", "dev", "--yes"], settings=settings) == 0

    assert "Freeze anyway?" not in capsys.readouterr().err
    assert frozen_at(ingested, "dev") is not None
