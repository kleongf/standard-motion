"""Compile: a Description becomes a Rubric draft through one Spark call (scripted here)."""

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import wait_for_job
from tests.rubric.scripted import ScriptedCompile, criterion, phrase
from winnow.app import create_app
from winnow.core.settings import Settings

DESCRIPTION = "Tidy pick: one grasp only, and no long pauses while holding."
ONE_GRASP = "one grasp only"
NO_PAUSES = "no long pauses while holding"


@pytest.fixture
def spark() -> ScriptedCompile:
    return ScriptedCompile(answers=[])


@pytest.fixture
def api(settings: Settings, spark: ScriptedCompile) -> Iterator[TestClient]:
    with TestClient(create_app(settings, transport=spark)) as client:
        yield client


def compile_description(api: TestClient, description: str = DESCRIPTION) -> Any:
    response = api.post("/api/rubric/draft/compile", json={"description": description})
    assert response.status_code == 200, response.text
    return response.json()


def test_a_description_compiles_to_phrases_linked_to_criteria(
    api: TestClient, spark: ScriptedCompile
):
    pause = criterion(
        "longest_still_s",
        "<",
        2.0,
        params={"speed_below_m_s": 0.01},
        window={"kind": "holding", "seconds": None},
        assumptions=["A long pause is 2 s or more under 1 cm/s."],
    )
    spark.answers.append(
        {
            "phrases": [
                phrase(
                    "Tidy pick", "context", reason="Names the task; the rest says what tidy is."
                ),
                phrase(ONE_GRASP, criteria=[criterion("grasp_attempts", "<=", 1)]),
                phrase(NO_PAUSES, criteria=[pause]),
            ]
        }
    )

    draft = compile_description(api)

    assert draft["description"] == DESCRIPTION
    phrases = draft["phrases"]
    assert [(p["text"], p["status"]) for p in phrases] == [
        ("Tidy pick", "context"),
        (ONE_GRASP, "checked"),
        (NO_PAUSES, "checked"),
    ]
    assert phrases[0]["reason"] == "Names the task; the rest says what tidy is."
    assert phrases[1]["restatement"] == f"Precisely: {ONE_GRASP}."
    assert (phrases[1]["start"], phrases[1]["end"]) == (11, 25)
    attempts, still = draft["criteria"]
    assert (attempts["phrase"], attempts["unit"], attempts["hard"]) == (ONE_GRASP, "attempts", True)
    assert still["phrase"] == NO_PAUSES
    assert still["assumptions"] == ["A long pause is 2 s or more under 1 cm/s."]
    assert draft["english"][attempts["id"]] == "Grasp attempts, up to and including the grasp, ≤ 1"
    assert draft["english"][still["id"]] == (
        "Longest stretch with the arm under 0.01 m/s, while holding, < 2 s"
    )
    assert draft["settings"]["gripper_closed_level"]["assumption"]  # assumed until confirmed
    assert api.get("/api/rubric/draft").json() == draft
    assert len(spark.prompts) == 1


def _no_speed_pause() -> dict[str, object]:
    """Invalid: longest_still_s needs its speed."""
    return criterion("longest_still_s", "<", 2.0, window={"kind": "holding", "seconds": None})


def _with_invalid_pause() -> dict[str, object]:
    return {
        "phrases": [
            phrase(ONE_GRASP, criteria=[criterion("grasp_attempts", "<=", 1)]),
            phrase(NO_PAUSES, criteria=[_no_speed_pause()]),
        ]
    }


def test_an_invalid_criterion_gets_one_repair_turn(api: TestClient, spark: ScriptedCompile):
    fixed = criterion("longest_still_s", "<", 2.0, params={"speed_below_m_s": 0.02})
    spark.answers += [_with_invalid_pause(), {"phrases": [phrase(NO_PAUSES, criteria=[fixed])]}]

    draft = compile_description(api)

    assert [(p["text"], p["status"]) for p in draft["phrases"]] == [
        (ONE_GRASP, "checked"),
        (NO_PAUSES, "checked"),
    ]
    assert [c["params"] for c in draft["criteria"]] == [{}, {"speed_below_m_s": 0.02}]
    first, repair = spark.prompts
    assert repair[0] == first[0]
    assert json.loads(repair[1]) == _with_invalid_pause()  # it sees its own answer
    assert "speed_below_m_s" in repair[2] and NO_PAUSES in repair[2]


def test_a_phrase_failing_its_repair_is_unsupported_with_the_error(
    api: TestClient, spark: ScriptedCompile
):
    still_invalid = {"phrases": [phrase(NO_PAUSES, criteria=[_no_speed_pause()])]}
    spark.answers += [_with_invalid_pause(), still_invalid]

    draft = compile_description(api)

    assert len(spark.prompts) == 2  # one repair turn, no more
    pauses = draft["phrases"][1]
    assert (pauses["text"], pauses["status"]) == (NO_PAUSES, "unsupported")
    assert "longest_still_s takes params ['speed_below_m_s']" in pauses["reason"]
    assert [c["primitive"] for c in draft["criteria"]] == ["grasp_attempts"]


def test_a_phrase_not_in_the_description_is_rejected_and_its_words_highlighted(
    api: TestClient, spark: ScriptedCompile
):
    pause = criterion("longest_still_s", "<", 2.0, params={"speed_below_m_s": 0.01})
    paraphrased = phrase("a single grasp", criteria=[criterion("grasp_attempts", "<=", 1)])
    spark.answers += [
        {"phrases": [paraphrased, phrase(NO_PAUSES, criteria=[pause])]},
        {"phrases": [paraphrased]},  # paraphrases again
    ]

    draft = compile_description(api)

    assert [p["text"] for p in draft["phrases"]] == [NO_PAUSES]
    assert [c["phrase"] for c in draft["criteria"]] == [NO_PAUSES]
    [rejected] = draft["rejected"]
    assert rejected["text"] == "a single grasp"
    assert "isn't an exact substring of the Description" in rejected["reason"]
    assert "isn't an exact substring" in spark.prompts[1][2]  # the repair turn said why
    # Every meaningful word outside a Phrase shows; "and" carries nothing on its own.
    assert [(w["text"], w["start"]) for w in draft["uncovered"]] == [
        ("Tidy", 0),
        ("pick", 5),
        ("one", 11),
        ("grasp", 15),
        ("only", 21),
    ]


def test_overlapping_phrases_are_rejected_by_code(api: TestClient, spark: ScriptedCompile):
    grasp = criterion("grasp_attempts", "<=", 1)
    spark.answers += [
        {"phrases": [phrase(ONE_GRASP, criteria=[grasp]), phrase("grasp only", criteria=[grasp])]},
        {"phrases": [phrase("grasp only", criteria=[grasp])]},
    ]

    draft = compile_description(api)

    assert [p["text"] for p in draft["phrases"]] == [ONE_GRASP]
    assert "overlaps another Phrase" in draft["rejected"][0]["reason"]


def test_spark_sees_the_catalog_with_ranges_over_the_anchor_pool_only(
    api: TestClient, spark: ScriptedCompile
):
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [0, 1, 2]})
    wait_for_job(api, job.json()["job_id"])
    api.post("/api/sets/dev/episodes", json={"episode_ids": ["droid_100:0", "droid_100:2"]})
    api.post("/api/sets/test/episodes", json={"episode_ids": ["droid_100:1"]})
    spark.answers.append({"phrases": []})

    compile_description(api)

    assert api.get("/api/anchor-pool").json() == {
        "set_name": "dev",
        "episode_ids": ["droid_100:0", "droid_100:2"],
        "hidden_test_episodes": 1,
        "awaiting_reference_label": 2,
    }
    [[prompt]] = spark.prompts
    assert "The anchor pool is the Dev set: 2 Episodes." in prompt
    # Episode 0 grasps first time; Episode 2 fails twice first.
    assert "- grasp_attempts() -> attempts:" in prompt
    assert "anchor pool 1 to 3, median 2 (2 of 2 Episodes)" in prompt
    assert "- longest_still_s(speed_below_m_s=0.01) -> s:" in prompt
    assert "15 Hz" in prompt and "frames 320x180 px" in prompt
    assert DESCRIPTION in prompt


def test_compiling_needs_the_meta_api(settings: Settings):
    with TestClient(create_app(settings)) as no_meta:
        response = no_meta.post("/api/rubric/draft/compile", json={"description": DESCRIPTION})
        assert no_meta.get("/api/rubric/draft").json() is None

    assert response.status_code == 503
    assert "MODEL_API_KEY" in response.json()["detail"]
