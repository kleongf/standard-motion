import pytest
from fastapi.testclient import TestClient

from tests.helpers import wait_for_job
from winnow.cli import main
from winnow.core.settings import Settings


@pytest.fixture
def ingested(api: TestClient) -> TestClient:
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [0, 1, 2]})
    wait_for_job(api, job.json()["job_id"])
    return api


def add(api: TestClient, name: str, *ids: str):
    return api.post(f"/api/sets/{name}/episodes", json={"episode_ids": list(ids)})


def sets(api: TestClient) -> dict[str, dict[str, object]]:
    return {s["name"]: s for s in api.get("/api/sets").json()}


def test_both_sets_start_empty_and_unfrozen(api: TestClient):
    assert sets(api) == {
        "dev": {"name": "dev", "size": 0, "frozen_at": None, "episode_ids": []},
        "test": {"name": "test", "size": 0, "frozen_at": None, "episode_ids": []},
    }


def test_the_route_defines_and_freezes_a_set(ingested: TestClient):
    assert add(ingested, "dev", "droid_100:1", "droid_100:0").status_code == 200
    assert add(ingested, "dev", "droid_100:2", "droid_100:1").status_code == 200  # top up

    frozen = ingested.post("/api/sets/dev/freeze", json={"force": True})

    assert frozen.status_code == 200
    dev = sets(ingested)["dev"]
    assert dev["episode_ids"] == ["droid_100:0", "droid_100:1", "droid_100:2"]
    assert dev["size"] == 3 and dev["frozen_at"] == frozen.json()["frozen_at"] is not None
    assert sets(ingested)["test"]["frozen_at"] is None


def test_changing_a_frozen_sets_membership_is_refused(ingested: TestClient):
    add(ingested, "test", "droid_100:0")
    frozen_at = ingested.post("/api/sets/test/freeze", json={"force": True}).json()["frozen_at"]

    added = add(ingested, "test", "droid_100:1")
    removed = ingested.delete("/api/sets/test/episodes/droid_100:0")
    again = ingested.post("/api/sets/test/freeze")

    assert added.status_code == removed.status_code == 409
    assert "frozen" in added.json()["detail"]
    assert again.status_code == 200 and again.json()["frozen_at"] == frozen_at
    assert sets(ingested)["test"]["episode_ids"] == ["droid_100:0"]


def test_an_episode_cant_be_in_both_sets(ingested: TestClient):
    add(ingested, "dev", "droid_100:1")

    response = add(ingested, "test", "droid_100:2", "droid_100:1")

    assert response.status_code == 409
    assert "droid_100:1 (Dev set)" in response.json()["detail"]
    assert sets(ingested)["test"]["episode_ids"] == []  # all or nothing


def test_only_ingested_episodes_can_join_a_set(ingested: TestClient):
    response = add(ingested, "dev", "droid_100:0", "droid_100:42")

    assert response.status_code == 422
    assert "droid_100:42" in response.json()["detail"]
    assert sets(ingested)["dev"]["size"] == 0


def test_before_freezing_an_episode_can_be_removed(ingested: TestClient):
    add(ingested, "dev", "droid_100:0", "droid_100:1")

    removed = ingested.delete("/api/sets/dev/episodes/droid_100:0")
    missing = ingested.delete("/api/sets/dev/episodes/droid_100:0")

    assert removed.status_code == 200 and removed.json()["episode_ids"] == ["droid_100:1"]
    assert missing.status_code == 404


def test_an_empty_set_cant_be_frozen(api: TestClient):
    assert api.post("/api/sets/dev/freeze").status_code == 422
    assert sets(api)["dev"]["frozen_at"] is None


def test_the_cli_defines_and_freezes_sets(
    ingested: TestClient, settings: Settings, capsys: pytest.CaptureFixture[str]
):
    assert main(["sets", "add", "dev", "droid_100:0", "droid_100:1"], settings=settings) == 0
    assert main(["sets", "remove", "dev", "droid_100:1"], settings=settings) == 0
    assert main(["sets", "freeze", "dev", "--yes"], settings=settings) == 0
    capsys.readouterr()

    refused = main(["sets", "add", "dev", "droid_100:2"], settings=settings)
    main(["sets", "show"], settings=settings)

    assert refused == 1
    out = capsys.readouterr()
    assert "can't change" in out.err
    assert "Dev set: 1 Episodes, frozen" in out.out and "droid_100:0" in out.out
    assert "Test set: 0 Episodes, not frozen" in out.out
    assert sets(ingested)["dev"]["episode_ids"] == ["droid_100:0"]
