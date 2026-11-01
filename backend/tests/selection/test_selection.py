import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.helpers import wait_for_job
from tests.meta.fakes import NoTranscribe
from winnow.app import create_app
from winnow.cli import main
from winnow.core.settings import Settings
from winnow.episodes.droid101 import EpisodeMeta
from winnow.meta.models import MetaContent
from winnow.meta.transport import Reply
from winnow.selection.service import sample_indices


@dataclass
class ScriptedSpark(NoTranscribe):
    images: int = 0
    seen: list[str] = field(default_factory=list[str])
    cut_off_first: int = 0  # the first N calls stop at the token cap with no answer

    async def upload(self, path: Path) -> str:
        return "file"

    async def count_tokens(self, model: str, content: MetaContent) -> int:
        return 1000

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        self.images += sum(1 for part in content if part["type"] == "input_image")
        self.seen.append(str(content[0]["text"]))
        if len(self.seen) <= self.cut_off_first:
            return Reply("", {"output_tokens": 4000}, incomplete="max_output_tokens")
        answer = {"pick_and_place": True, "object": "marker", "target": "bowl"}
        return Reply(json.dumps(answer), {"input_tokens": 800, "output_tokens": 200})


def meta(index: int, success: bool) -> EpisodeMeta:
    return EpisodeMeta(index=index, length=30, flagged_success=success, task=None, row={})


def test_the_same_seed_draws_the_same_sample_mostly_of_flagged_failures():
    episodes = [meta(i, success=i % 5 != 0) for i in range(1000)]  # 200 failures

    first = sample_indices(episodes, size=100, seed=7)

    assert first == sample_indices(episodes, size=100, seed=7)
    assert first != sample_indices(episodes, size=100, seed=8)
    assert len(first) == 100
    assert sum(1 for i in first if i % 5 == 0) == 80


@pytest.fixture
def spark() -> ScriptedSpark:
    return ScriptedSpark()


@pytest.fixture
def selected(settings: Settings, spark: ScriptedSpark) -> Iterator[TestClient]:
    assert main(["select", "droid_1.0.1", "--size", "4", "--seed", "1"], settings, spark) == 0
    with TestClient(create_app(settings, transport=spark)) as client:
        yield client


def test_the_selection_pass_gives_a_candidate_with_a_contact_sheet_per_sampled_episode(
    selected: TestClient, spark: ScriptedSpark
):
    candidates = selected.get("/api/selection").json()

    assert sorted(c["episode_id"] for c in candidates) == [f"droid_1.0.1:{i}" for i in range(4)]
    assert spark.images == 4
    assert "pick-and-place" in spark.seen[0]
    first = candidates[0]
    assert (first["pick_and_place"], first["object"], first["target"]) == (True, "marker", "bowl")
    assert first["status"] == "pending"
    sheet = selected.get(f"/api/selection/{first['episode_id']}/sheet")
    assert sheet.status_code == 200 and sheet.headers["content-type"] == "image/jpeg"


def test_rerunning_the_selection_pass_adds_no_calls(settings: Settings, spark: ScriptedSpark):
    main(["select", "droid_1.0.1", "--size", "4", "--seed", "1"], settings, spark)
    main(["select", "droid_1.0.1", "--size", "4", "--seed", "1"], settings, spark)

    assert spark.images == 4


def test_excluding_a_candidate_needs_one_of_the_two_reasons(selected: TestClient):
    url = "/api/selection/droid_1.0.1:1"

    assert selected.put(url, json={"decision": "exclude"}).status_code == 422
    assert selected.put(url, json={"decision": "exclude", "reason": "failed"}).status_code == 422
    ok = selected.put(url, json={"decision": "exclude", "reason": "object too small to see"})

    assert ok.status_code == 200
    assert (ok.json()["status"], ok.json()["exclusion_reason"]) == (
        "excluded",
        "object too small to see",
    )


def test_confirmed_candidates_are_ingested_with_their_object_and_target(selected: TestClient):
    selected.put("/api/selection/droid_1.0.1:0", json={"decision": "confirm"})
    selected.put("/api/selection/droid_1.0.1:2", json={"decision": "confirm"})
    selected.put(
        "/api/selection/droid_1.0.1:3", json={"decision": "exclude", "reason": "not pick-and-place"}
    )

    job = selected.post("/api/selection/ingest")
    wait_for_job(selected, job.json()["job_id"])

    episodes = {e["id"]: e for e in selected.get("/api/episodes").json()}
    assert sorted(episodes) == ["droid_1.0.1:0", "droid_1.0.1:2"]
    assert (episodes["droid_1.0.1:2"]["task_object"], episodes["droid_1.0.1:2"]["task_target"]) == (
        "marker",
        "bowl",
    )


def test_the_selection_screen_never_sees_the_dataset_outcome(selected: TestClient):
    body = selected.get("/api/selection").text

    assert "success" not in body and "outcome" not in body


def test_a_cut_off_answer_still_gives_a_candidate_and_a_rerun_retries_it(
    settings: Settings, spark: ScriptedSpark
):
    spark.cut_off_first = 1
    assert main(["select", "droid_1.0.1", "--size", "4", "--seed", "1"], settings, spark) == 1

    with TestClient(create_app(settings, transport=spark)) as api:
        failed = [c for c in api.get("/api/selection").json() if c["error"]]
        assert len(failed) == 1 and "stopped early" in failed[0]["error"]
        assert failed[0]["pick_and_place"] is None

    assert main(["select", "droid_1.0.1", "--size", "4", "--seed", "1"], settings, spark) == 0
    assert spark.images == 5  # only the cut-off one was asked again
