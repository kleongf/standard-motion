"""Compile can choose `ask_video`: Spark sees it in the capabilities manifest and writes the
frozen question and paraphrases, which code checks."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tests.rubric.scripted import ScriptedCompile, criterion, phrase
from tests.visual.answers import PARAPHRASES, QUESTION
from winnow.app import create_app
from winnow.core.settings import Settings

DESCRIPTION = "Tidy place: puts the cup on the saucer."
ON_SAUCER = "puts the cup on the saucer"


@pytest.fixture
def spark() -> ScriptedCompile:
    return ScriptedCompile(answers=[])


@pytest.fixture
def api(settings: Settings, spark: ScriptedCompile) -> Iterator[TestClient]:
    with TestClient(create_app(settings, transport=spark)) as client:
        yield client


def visual(**fields: object) -> dict[str, object]:
    asked: dict[str, object] = {
        "window": {"kind": "after_release", "seconds": None},
        "views": ["exterior_image_1_left"],
        "question": QUESTION,
        "paraphrases": PARAPHRASES,
        "crop": "placement",
    }
    return criterion("ask_video", ">=", 3, **(asked | fields))


def compile_with(api: TestClient, spark: ScriptedCompile, *answers: object) -> dict[str, object]:
    spark.answers.extend(answers)
    response = api.post("/api/rubric/draft/compile", json={"description": DESCRIPTION})
    assert response.status_code == 200, response.text
    return response.json()


def test_spark_sees_ask_video_and_how_to_ask_it(api: TestClient, spark: ScriptedCompile):
    compile_with(api, spark, {"phrases": []})

    [[prompt]] = spark.prompts
    assert "- ask_video() -> samples:" in prompt
    assert "question" in prompt and "2 paraphrases" in prompt
    assert "placement" in prompt


def test_a_phrase_compiles_to_a_visual_criterion_with_its_frozen_question(
    api: TestClient, spark: ScriptedCompile
):
    draft = compile_with(
        api,
        spark,
        {
            "phrases": [
                phrase("Tidy place", "context", reason="The task."),
                phrase(ON_SAUCER, criteria=[visual()]),
            ]
        },
    )

    [asked] = draft["criteria"]  # type: ignore[misc]
    assert (asked["kind"], asked["question"], asked["crop"]) == ("visual", QUESTION, "placement")
    assert asked["paraphrases"] == PARAPHRASES
    english = draft["english"][asked["id"]]  # type: ignore[index]
    assert english == (
        "Spark, on the view the object was boxed in after release, cropped to the object and its "
        "target: "
        f'"{QUESTION}"'
    )


def test_a_visual_criterion_without_its_paraphrases_gets_a_repair_turn(
    api: TestClient, spark: ScriptedCompile
):
    bad = {"phrases": [phrase(ON_SAUCER, criteria=[visual(paraphrases=[])])]}
    fixed = {"phrases": [phrase(ON_SAUCER, criteria=[visual()])]}

    draft = compile_with(api, spark, bad, fixed)

    assert "2 paraphrases" in spark.prompts[1][-1]
    assert [c["kind"] for c in draft["criteria"]] == ["visual"]  # type: ignore[union-attr]
