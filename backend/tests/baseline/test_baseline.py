import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tests.baseline.scripted import REASON, ScriptedSpark
from tests.conftest import CORRUPT_EPISODE
from tests.helpers import app_context, wait_for_job
from winnow.app import create_app
from winnow.baseline.prompts import FROZEN_DESCRIPTION, Description
from winnow.baseline.service import SKIPPED_NO_INSTRUCTION, run_baseline
from winnow.core.settings import Settings


@pytest.fixture
def spark() -> ScriptedSpark:
    return ScriptedSpark()


@pytest.fixture
def app_api(settings: Settings, spark: ScriptedSpark) -> Iterator[TestClient]:
    with TestClient(create_app(settings, transport=spark)) as client:
        yield client


def ingest(api: TestClient, *indices: int) -> dict[str, object]:
    response = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": indices})
    return wait_for_job(api, response.json()["job_id"])


def test_each_ingested_episode_gets_three_samples_and_a_failbench_answer(
    app_api: TestClient, spark: ScriptedSpark
):
    job = ingest(app_api, 0, 1)

    assert job["done"] == 6 and job["failed"] == 0  # ingest, baseline, wrist track per Episode
    assert (spark.baseline_calls, spark.failbench_calls) == (6, 2)
    answers = app_context(app_api).baseline.answers("droid_100:1", FROZEN_DESCRIPTION)
    assert [a.sample for a in answers.samples] == [0, 1, 2]
    assert answers.samples[0].answer is not None
    assert answers.samples[0].answer.decision == "reject"
    assert answers.failbench is not None and answers.failbench.answer is not None
    assert answers.failbench.answer.success is True
    assert app_api.get("/api/dataset").json()["baseline"] == 2


def test_the_prompt_carries_the_description_and_the_instruction(
    app_api: TestClient, spark: ScriptedSpark
):
    ingest(app_api, 1)

    baseline_prompt = next(p for p in spark.prompts if FROZEN_DESCRIPTION in p)
    assert "Move the black remote control to the left" in baseline_prompt


def test_rerunning_is_all_cache_hits_but_a_new_description_is_not(
    app_api: TestClient, spark: ScriptedSpark
):
    ingest(app_api, 0)
    ingest(app_api, 0)
    assert spark.baseline_calls == 3

    ctx = app_context(app_api)
    [episode] = ctx.episodes.list()
    assert ctx.meta is not None
    other = Description("Expert: no long pauses.", ("no long pauses",))
    asyncio.run(run_baseline(ctx.meta, ctx.baseline, ctx.episodes, episode, other))

    assert spark.baseline_calls == 6
    assert spark.failbench_calls == 1  # the success check doesn't depend on the Description


def test_a_malformed_answer_fails_only_its_own_sample(app_api: TestClient, spark: ScriptedSpark):
    spark.malformed_calls = {2}

    job = ingest(app_api, 0)

    baseline_item = job["items"][1]  # type: ignore[index]
    assert baseline_item["status"] == "done"
    assert baseline_item["detail"] == "1 of 4 answers failed"
    answers = app_context(app_api).baseline.answers("droid_100:0", FROZEN_DESCRIPTION)
    assert [a.error is None for a in answers.samples].count(False) == 1
    assert sum(a.answer is not None for a in answers.samples) == 2
    assert app_api.get("/api/dataset").json()["baseline"] == 0  # incomplete


def test_no_baseline_without_its_episode(app_api: TestClient, spark: ScriptedSpark):
    job = ingest(app_api, CORRUPT_EPISODE)

    assert [i["status"] for i in job["items"]] == ["failed"] * 3  # type: ignore[union-attr]
    assert job["items"][1]["detail"] == f"skipped: droid_100:{CORRUPT_EPISODE} failed"  # type: ignore[index]
    assert spark.baseline_calls == 0


def test_an_episode_without_an_instruction_is_not_judged_until_it_has_one(
    app_api: TestClient, spark: ScriptedSpark
):
    job = ingest(app_api, 2)  # the fixture's Episode 2 has no instruction

    baseline_item = job["items"][1]  # type: ignore[index]
    assert (baseline_item["status"], baseline_item["detail"]) == ("done", SKIPPED_NO_INSTRUCTION)
    assert (spark.baseline_calls, spark.failbench_calls) == (0, 0)
    answers = app_context(app_api).baseline.answers("droid_100:2", FROZEN_DESCRIPTION)
    assert (answers.samples, answers.failbench) == ([], None)


def test_no_response_the_ui_reads_shows_a_baseline_result(app_api: TestClient):
    job = ingest(app_api, 0)

    for path in ("/api/episodes", "/api/dataset", "/api/boxes", f"/api/jobs/{job['id']}"):
        body = app_api.get(path).text
        assert REASON not in body and "reject" not in body.lower(), path


def test_without_a_meta_api_key_there_is_no_baseline(api: TestClient):
    job = ingest(api, 0)

    assert job["total"] == 1
    assert api.get("/api/dataset").json()["baseline"] is None
