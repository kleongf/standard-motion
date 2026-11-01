"""The dry run: once a Description compiles, Spark is asked the draft's visual Criteria on the
anchor pool in the background, so the Describe page shows their pass rates before Run."""

import asyncio
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import app_context, reference_label, wait_for_job
from tests.interview.client import answer, interview, say, skip_to
from tests.interview.scripted_text import ScriptedText
from tests.rubric.scripted import phrase, video_criterion
from tests.visual.answers import PARAPHRASES, QUESTION
from tests.visual.scripted import CompileAndAsk, ScriptedVisual, response_format
from winnow.app import create_app
from winnow.core.settings import Settings
from winnow.meta.models import MetaContent
from winnow.meta.transport import Reply
from winnow.visual.service import DRY_RUN

ON_SAUCER = "puts the cup on the saucer"
DESCRIPTION = f"Tidy place: {ON_SAUCER}."
DEV = ["droid_100:0", "droid_100:1", "droid_100:2"]  # the anchor pool; Episode 4 is outside it
OPEN_GRIPPER = "droid_100:4"  # never grasps, so has no window after a release


def compile_answer() -> dict[str, object]:
    return {
        "phrases": [
            phrase("Tidy place", "context", reason="Names the task."),
            phrase(ON_SAUCER, criteria=[video_criterion(QUESTION, PARAPHRASES)]),
        ]
    }


@dataclass
class HeldVisual(CompileAndAsk):
    """Holds every visual answer until `answering` is set."""

    answering: threading.Event = field(default_factory=threading.Event)

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        if response_format(options) == "visual":
            await asyncio.to_thread(self.answering.wait, 10)
        return await super().respond(model, content, options)


@pytest.fixture
def spark() -> HeldVisual:
    # Episode 1's samples all answer fail; Episode 0's all pass.
    held = HeldVisual(
        ScriptedText(answers=[]), ScriptedVisual({"000001": ("fail", "fail", "fail")})
    )
    held.answering.set()
    return held


@pytest.fixture
def api(settings: Settings, spark: CompileAndAsk) -> Iterator[TestClient]:
    with TestClient(create_app(settings, transport=spark)) as client:
        job = client.post(
            "/api/episodes/ingest", json={"source": "droid_100", "indices": [0, 1, 2, 4]}
        )
        wait_for_job(client, job.json()["job_id"])
        client.post("/api/sets/dev/episodes", json={"episode_ids": DEV})
        for episode_id in DEV:
            reference_label(client, episode_id)
        yield client


def compile_draft(api: TestClient, spark: CompileAndAsk) -> Any:
    spark.compile.answers.append(compile_answer())
    response = api.post("/api/rubric/draft/compile", json={"description": DESCRIPTION})
    assert response.status_code == 200, response.text
    return response.json()


def latest_dry_run(api: TestClient) -> Any:
    return api.get("/api/jobs/latest", params={"kind": DRY_RUN}).json()


def finished_dry_run(api: TestClient) -> Any:
    job = latest_dry_run(api)
    assert job is not None, "no dry run was queued"
    return wait_for_job(api, job["id"])


def test_a_compile_asks_the_visual_criteria_on_the_anchor_pool_only(
    api: TestClient, spark: CompileAndAsk
):
    compile_draft(api, spark)

    job = finished_dry_run(api)

    assert (job["done"], job["failed"]) == (6, 0)  # a crop and a visual item per Episode
    asked = {call.clip.split("/")[0] for call in spark.visual.calls}
    assert asked == {"000000", "000001", "000002"}
    assert len(spark.visual.calls) == 9  # 3 samples on each anchor Episode


def preview(api: TestClient) -> Any:
    response = api.post("/api/rubric/draft/preview", json={})
    assert response.status_code == 200, response.text
    [placed] = response.json()["criteria"]
    return placed


def test_the_dry_runs_answers_turn_not_asked_into_a_pass_rate(
    api: TestClient, spark: CompileAndAsk
):
    compile_draft(api, spark)

    finished_dry_run(api)

    found = preview(api)
    assert (found["passing"], found["failing"], found["unsure"]) == (2, 1, 0)
    assert found["fail_rate"]["count"] == 1 and found["fail_rate"]["of"] == 3  # sanity monitor


def test_compiling_again_with_the_same_ask_keys_queues_nothing(
    api: TestClient, spark: CompileAndAsk
):
    compile_draft(api, spark)
    first = finished_dry_run(api)

    compile_draft(api, spark)

    assert latest_dry_run(api)["id"] == first["id"]
    assert len(spark.visual.calls) == 9


def test_a_grasp_setting_edit_asks_again_under_its_new_ask_keys(
    api: TestClient, spark: CompileAndAsk
):
    compile_draft(api, spark)
    first = finished_dry_run(api)

    edited = api.patch("/api/rubric/draft", json={"grasp_rise_m": 0.03})
    assert edited.status_code == 200, edited.text

    again = finished_dry_run(api)
    assert again["id"] != first["id"]
    assert [i["label"] for i in again["items"]] == [i["label"] for i in first["items"]]


def test_a_switched_off_visual_criterion_is_asked_once_switched_on(
    api: TestClient, spark: CompileAndAsk
):
    [placed] = compile_draft(api, spark)["criteria"]
    first = finished_dry_run(api)
    api.patch("/api/rubric/draft", json={"criteria": {placed["id"]: {"enabled": False}}})

    api.patch("/api/rubric/draft", json={"grasp_rise_m": 0.03})
    assert latest_dry_run(api)["id"] == first["id"]

    api.patch("/api/rubric/draft", json={"criteria": {placed["id"]: {"enabled": True}}})
    assert finished_dry_run(api)["id"] != first["id"]


def test_an_edit_while_the_dry_run_asks_queues_nothing_more(api: TestClient, spark: HeldVisual):
    spark.answering.clear()
    [placed] = compile_draft(api, spark)["criteria"]
    asking = latest_dry_run(api)

    edited = api.patch("/api/rubric/draft", json={"criteria": {placed["id"]: {"threshold": 2}}})
    assert edited.status_code == 200, edited.text

    assert latest_dry_run(api)["id"] == asking["id"]
    spark.answering.set()
    assert finished_dry_run(api)["failed"] == 0


def test_over_budget_the_items_fail_and_the_criterion_stays_not_asked(
    api: TestClient, spark: HeldVisual
):
    spark.answering.clear()
    [placed] = compile_draft(api, spark)["criteria"]
    meta = app_context(api).meta
    assert meta is not None
    meta.costs.budget_usd = 0.0
    spark.answering.set()

    job = finished_dry_run(api)

    visual = [i for i in job["items"] if i["step"] == "visual"]
    assert [i["status"] for i in visual] == ["failed"] * 3
    assert all("budget" in i["detail"] for i in visual)
    assert preview(api)["unsure"] == 3
    api.patch("/api/rubric/draft", json={"grasp_rise_m": 0.03})
    assert latest_dry_run(api)["id"] == job["id"]  # with the budget spent, it isn't asked again
    assert api.post("/api/rubric/draft/run").status_code == 201
    triage = api.get("/api/episodes/droid_100:0/triage").json()
    found = next(c for c in triage["criteria"] if c["criterion_id"] == placed["id"])
    assert found["measurement"] == "not asked"


def test_without_the_meta_api_an_edit_queues_nothing(
    api: TestClient, spark: CompileAndAsk, settings: Settings
):
    compile_draft(api, spark)
    asked = finished_dry_run(api)
    with TestClient(create_app(settings)) as offline:  # the same data dir, no Meta API
        edited = offline.patch("/api/rubric/draft", json={"grasp_rise_m": 0.03})

        assert edited.status_code == 200, edited.text
        assert latest_dry_run(offline)["id"] == asked["id"]


def test_an_anchor_episode_with_no_window_is_not_asked_again(api: TestClient, spark: HeldVisual):
    api.post("/api/sets/dev/episodes", json={"episode_ids": [OPEN_GRIPPER]})
    compile_draft(api, spark)
    first = finished_dry_run(api)
    nothing = [i for i in first["items"] if i["label"].startswith(OPEN_GRIPPER)]
    assert [i["detail"] for i in nothing] == [
        "window empty: nothing to ask",
        "no clip to ask about",
    ]

    compile_draft(api, spark)

    assert latest_dry_run(api)["id"] == first["id"]


def test_an_interview_answer_that_settles_a_grasp_setting_asks_again(
    api: TestClient, spark: HeldVisual
):
    compile_draft(api, spark)
    first = finished_dry_run(api)
    skip_to(api, "setting")
    answer(api, "skip")  # the closed level
    answer(api, "fail")  # Episode 2's failed attempts rise 0 cm
    assert latest_dry_run(api)["id"] == first["id"]  # bisecting: the setting is unchanged yet

    answer(api, "pass")  # Episode 0 or 1 lifts its grasp: the grasp rise is set

    again = finished_dry_run(api)
    assert again["id"] != first["id"]
    undone = api.delete(f"/api/interview/answers/{interview(api)['answered'][-2]['id']}")
    assert undone.status_code == 200, undone.text
    assert latest_dry_run(api)["id"] == again["id"]  # the setting is back: answered already


def test_words_that_edit_the_description_ask_its_new_visual_criterion(
    api: TestClient, spark: HeldVisual
):
    compile_draft(api, spark)
    first = finished_dry_run(api)
    upright = "keeps it upright"
    edited = DESCRIPTION.replace(".", f", and {upright}.")
    spark.compile.texts.append({"description": edited, "reply": "Added it."})
    asked = video_criterion(
        "Does the cup stay upright?", ["Is it kept upright?", "Does it stay upright?"]
    )
    spark.compile.answers.append({"phrases": [phrase(upright, criteria=[asked])]})

    say(api, "It should also keep the cup upright.", None)

    again = finished_dry_run(api)
    assert again["id"] != first["id"]
    assert len(again["items"]) == 6  # only the new Criterion, on each anchor Episode
    assert len(spark.visual.calls) == 18
