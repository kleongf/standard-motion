"""e2e's interview specs under the replay transport: the calls `tests.record_interview` scripted
replay. The disagree compile's Phrase's Criteria disagree on e2e's Dev set Episode, and the
curator's own words answer STEADY's first question or edit its Description."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import reference_label, wait_for_job
from tests.interview.client import say, skip_to
from tests.record_interview import (
    CAREFUL,
    CHANGE_TEXT,
    CHANGED,
    DISAGREE,
    EDIT_TEXT,
    EDITED,
    INTERVIEW_ANSWERS,
    NEVER_DROPS,
    PICK_TEXT,
    PICKED,
    STEADY,
    STEADY_EDITED,
    WITHIN,
)
from tests.record_meta import E2E_DEV_SET, E2E_EPISODES, RECORDINGS
from winnow.app import create_app
from winnow.core.settings import Settings
from winnow.episodes.fixtures import write_fixture_source
from winnow.meta.replay import ReplayTransport

DEV = [f"droid_100:{i}" for i in E2E_DEV_SET]


@pytest.fixture(scope="module")
def droid100_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """e2e's fixture source, which the compile was recorded against."""
    return write_fixture_source(tmp_path_factory.mktemp("droid_100"), episodes=E2E_EPISODES)


@pytest.fixture
def replay_api(settings: Settings, tmp_path: Path) -> Iterator[TestClient]:
    replies = tmp_path / "replies.jsonl"
    replies.write_text(RECORDINGS.read_text() + INTERVIEW_ANSWERS.read_text())
    with TestClient(create_app(settings, transport=ReplayTransport(replies))) as client:
        body = {"source": "droid_100", "indices": list(E2E_DEV_SET)}
        wait_for_job(client, client.post("/api/episodes/ingest", json=body).json()["job_id"])
        client.post("/api/sets/dev/episodes", json={"episode_ids": DEV})
        for episode in DEV:
            reference_label(client, episode)
        yield client


def test_the_scripted_compile_replays_and_its_criteria_disagree_on_the_dev_set(
    replay_api: TestClient,
):
    compiled = replay_api.post("/api/rubric/draft/compile", json={"description": DISAGREE})
    assert compiled.status_code == 200, compiled.text

    question = skip_to(replay_api, "disagree")

    assert (question["phrase"], question["episode_id"]) == (CAREFUL, DEV[0])
    assert [r["status"] for r in question["results"]] == ["pass", "fail"]
    assert question["measurement"] == "1 fails, 1 passes"


def steady(api: TestClient) -> Any:
    """STEADY compiled afresh: returns the question asked first."""
    compiled = api.post("/api/rubric/draft/compile", json={"description": STEADY, "fresh": True})
    assert compiled.status_code == 200, compiled.text
    return api.get("/api/interview").json()["question"]


def test_the_scripted_words_pick_an_answer_or_compile_the_phrase_again(replay_api: TestClient):
    question = steady(replay_api)
    assert question["text"] == NEVER_DROPS

    picked = say(replay_api, PICK_TEXT, question["key"])

    assert picked["reply"] == PICKED
    assert picked["interview"]["answered"][-1]["answer"] == "context"

    changed = say(replay_api, CHANGE_TEXT, steady(replay_api)["key"])

    assert changed["reply"] == CHANGED
    assert [(c["phrase"], c["id"]) for c in changed["draft"]["criteria"]] == [
        ("grasps it once", "grasp-attempts"),
        (NEVER_DROPS, "grasp-attempts-2"),
    ]


def test_the_scripted_words_with_no_question_edit_the_description(replay_api: TestClient):
    steady(replay_api)

    edited = say(replay_api, EDIT_TEXT, None)

    assert (edited["reply"], edited["draft"]["description"]) == (EDITED, STEADY_EDITED)
    assert [r["text"] for r in edited["draft"]["recompiled"]] == [WITHIN]
