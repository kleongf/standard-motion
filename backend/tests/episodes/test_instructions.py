"""`standard-motion instructions`: an instruction for each Episode its source shipped without one,
from the object and target Spark named, or by hand; never over one already there."""

import pytest
from fastapi.testclient import TestClient

from standard_motion.cli import main
from standard_motion.core.settings import Settings
from tests.helpers import app_context, wait_for_job

BLANK = "droid_100:2"  # the fixture source ships it with no instruction


@pytest.fixture
def ingested(api: TestClient) -> TestClient:
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [0, 2]})
    wait_for_job(api, job.json()["job_id"])
    return api


def instructions(api: TestClient) -> dict[str, str | None]:
    return {e["id"]: e["instruction"] for e in api.get("/api/episodes").json()}


def test_fill_writes_spark_names_into_blank_instructions_only(
    ingested: TestClient, settings: Settings, capsys: pytest.CaptureFixture[str]
):
    shipped = instructions(ingested)["droid_100:0"]
    app_context(ingested).episodes.set_task(BLANK, "marker", "pot")

    assert main(["instructions", "fill"], settings) == 0
    assert main(["instructions", "fill"], settings) == 0  # a second fill finds nothing to do

    assert instructions(ingested) == {
        "droid_100:0": shipped,
        BLANK: "Put the marker in or on the pot",
    }
    out = capsys.readouterr().out
    assert out.splitlines() == [
        "wrote 1 instructions from Spark's names",
        "wrote 0 instructions from Spark's names",
    ]


def test_fill_lists_episodes_spark_named_nothing_for(
    ingested: TestClient, settings: Settings, capsys: pytest.CaptureFixture[str]
):
    assert main(["instructions", "fill"], settings) == 0

    assert instructions(ingested)[BLANK] is None
    assert f"1 still without one (no object or target named): {BLANK}" in capsys.readouterr().out


def test_write_sets_one_by_hand_but_never_replaces_one(ingested: TestClient, settings: Settings):
    assert main(["instructions", "write", BLANK, " Put the cup in the sink "], settings) == 0
    assert main(["instructions", "write", BLANK, "Something else"], settings) == 1
    assert main(["instructions", "write", "droid_100:0", "Something else"], settings) == 1

    assert instructions(ingested)[BLANK] == "Put the cup in the sink"
