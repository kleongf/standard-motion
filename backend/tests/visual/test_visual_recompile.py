"""After a Description edit, a visual Criterion whose prompts render identically is a cache hit:
only the changed visual Criteria call Spark."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tests.helpers import ask_visual, reference_label, wait_for_job
from tests.interview.scripted_text import ScriptedText
from tests.rubric.scripted import phrase, video_criterion
from tests.visual.answers import PARAPHRASES, QUESTION
from tests.visual.scripted import CompileAndAsk, ScriptedVisual
from winnow.app import create_app
from winnow.core.settings import Settings

ON_SAUCER = "puts the cup on the saucer"
UPRIGHT = "keeps it upright"
LEVEL = "keeps it level"
DESCRIPTION = f"Tidy place: {ON_SAUCER}, and {UPRIGHT}."
EPISODE = "droid_100:0"


def stays(word: str) -> dict[str, object]:
    return video_criterion(
        f"Does the cup stay {word} throughout?",
        [f"Is the cup kept {word} the whole time?", f"Does the cup remain {word} all along?"],
    )


@pytest.fixture
def spark() -> CompileAndAsk:
    return CompileAndAsk(ScriptedText(answers=[]), ScriptedVisual())


@pytest.fixture
def api(settings: Settings, spark: CompileAndAsk) -> Iterator[TestClient]:
    with TestClient(create_app(settings, transport=spark)) as client:
        job = client.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [0]})
        wait_for_job(client, job.json()["job_id"])
        reference_label(client, EPISODE)
        yield client


def compile_and_run(api: TestClient, spark: CompileAndAsk, description: str, answer: object):
    spark.compile.answers.append(answer)
    compiled = api.post("/api/rubric/draft/compile", json={"description": description})
    assert compiled.status_code == 200, compiled.text
    assert api.post("/api/rubric/draft/run").status_code == 201
    return compiled.json()


def test_only_the_edited_visual_criterion_calls_spark(api: TestClient, spark: CompileAndAsk):
    on_saucer = phrase(ON_SAUCER, criteria=[video_criterion(QUESTION, PARAPHRASES)])
    first = compile_and_run(
        api,
        spark,
        DESCRIPTION,
        {"phrases": [on_saucer, phrase(UPRIGHT, criteria=[stays("upright")])]},
    )
    ask_visual(api, EPISODE)
    assert len(spark.visual.calls) == 6  # 2 visual Criteria, 3 prompts each

    edited = compile_and_run(
        api,
        spark,
        DESCRIPTION.replace(UPRIGHT, LEVEL),
        {"phrases": [phrase(LEVEL, criteria=[stays("level")])]},
    )
    ask_visual(api, EPISODE)

    asked_again = spark.visual.calls[6:]
    assert len(asked_again) == 3  # the placement question's answers were cache hits
    assert all("level" in c.prompt for c in asked_again)
    kept = next(c for c in edited["criteria"] if c["phrase"] == ON_SAUCER)
    assert kept["id"] == next(c for c in first["criteria"] if c["phrase"] == ON_SAUCER)["id"]
    triage = api.get(f"/api/episodes/{EPISODE}/triage").json()
    placed = next(c for c in triage["criteria"] if c["criterion_id"] == kept["id"])
    assert len(placed["visual"]["samples"]) == 3  # answered, from the cache
