"""Driving the Describe interview through its API, on a scripted compile of a small Description
against fixture Episodes 0-2 as the anchor pool."""

from typing import Any

from fastapi.testclient import TestClient

from tests.rubric.scripted import ScriptedCompile, criterion, phrase

DESCRIPTION = "Tidy pick: one grasp only, never drops it, smoothly, and no long pauses."
ONE_GRASP = "one grasp only"
NEVER_DROPS = "never drops it"
NO_PAUSES = "no long pauses"
# Fixture Episode i grasps once unless i % 3 == 2, which makes 3 attempts; none pauses at all.
DEV = ["droid_100:0", "droid_100:1", "droid_100:2"]


def pauses_phrase(text: str = NO_PAUSES) -> dict[str, object]:
    # 0.1 s: every anchor Episode's 0 s pause sits within its 0.2 s noise floor.
    pauses = criterion(
        "longest_still_s",
        "<",
        0.1,
        params={"speed_below_m_s": 0.01},
        assumptions=["A long pause is 0.1 s or more."],
    )
    return phrase(text, criteria=[pauses])


# Fixture Episode 2's three grasp attempts fail TIDY's first Criterion; no anchor Episode pauses,
# so all pass its second: its Criteria disagree on Episode 2.
TIDY = "grasps it once without pausing"
TIDY_DESCRIPTION = f"A tidy pick: {TIDY}."


def tidy_phrase(text: str = TIDY) -> dict[str, object]:
    grasps = criterion("grasp_attempts", "<=", 1, assumptions=["One attempt is the most."])
    pauses = criterion("longest_still_s", "<", 5, params={"speed_below_m_s": 0.01})
    return phrase(text, criteria=[grasps, pauses])


def compile_answer() -> dict[str, object]:
    grasps = criterion("grasp_attempts", "<=", 1, assumptions=["One attempt is the most."])
    return {
        "phrases": [
            phrase("Tidy pick", "context", reason="Names the task."),
            phrase(ONE_GRASP, criteria=[grasps]),
            phrase(NEVER_DROPS, "unsupported", reason="Nothing tracks the object yet."),
            pauses_phrase(),
        ]
    }


def interview(api: TestClient) -> Any:
    response = api.get("/api/interview")
    assert response.status_code == 200, response.text
    return response.json()


def answer(api: TestClient, value: str) -> Any:
    """Answer the question code is asking now."""
    question = interview(api)["question"]
    body = {"key": question["key"], "episode_id": question.get("episode_id"), "answer": value}
    response = api.post("/api/interview/answers", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def say(api: TestClient, text: str, key: str | None) -> Any:
    """The curator's own words: to the question with `key`, or, with None, about the
    Description."""
    response = api.post("/api/interview/text", json={"text": text, "question_key": key})
    assert response.status_code == 200, response.text
    return response.json()


def skip_to(api: TestClient, kind: str | None) -> Any:
    """Past every question before the first of `kind` (None: every question): Phrases left
    unchecked, the rest skipped. Returns that question, or None when none is left."""
    while (question := interview(api)["question"]) is not None and question["kind"] != kind:
        answer(api, "accept" if question["kind"] in ("phrase", "words") else "skip")
    return question


def criterion_of(api: TestClient, phrase_text: str) -> Any:
    draft = api.get("/api/rubric/draft").json()
    return next(c for c in draft["criteria"] if c["phrase"] == phrase_text)


def phrase_statuses(api: TestClient) -> dict[str, str]:
    return {p["text"]: p["status"] for p in api.get("/api/rubric/draft").json()["phrases"]}


def recompile(api: TestClient, spark: ScriptedCompile, edited: str, *phrases: object) -> None:
    spark.answers.append({"phrases": list(phrases)})
    response = api.post("/api/rubric/draft/compile", json={"description": edited})
    assert response.status_code == 200, response.text
    assert response.json()["recompiled"] is not None  # only the edit was compiled
