"""Free-text answers in the Describe interview: Spark maps the curator's words onto the question
being asked, or recompiles only the asked Phrase with them; with no question, it edits the
Description, which recompiles as an edit does."""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import app_context
from tests.interview.client import (
    DESCRIPTION,
    NEVER_DROPS,
    NO_PAUSES,
    ONE_GRASP,
    TIDY,
    answer,
    criterion_of,
    interview,
    phrase_statuses,
    say,
    skip_to,
)
from tests.interview.scripted_text import ScriptedText
from tests.rubric.scripted import criterion, phrase
from winnow.app import create_app
from winnow.core.settings import Settings
from winnow.interview.models import AnswerDraw
from winnow.interview.service import answer as answer_now


@pytest.fixture
def spark() -> ScriptedText:
    return ScriptedText(answers=[])


def mapped(choice: str, reply: str = "Got it.") -> dict[str, object]:
    return {"choice": choice, "reply": reply}


def test_text_mapped_to_an_option_answers_the_phrase_question_as_that_option(
    drafted: TestClient, spark: ScriptedText
):
    question = interview(drafted)["question"]
    assert question["text"] == NEVER_DROPS
    spark.texts.append(mapped("context", "Marked it Context."))

    said = say(drafted, "That's just how it looks, nothing to check.", question["key"])

    assert said["reply"] == "Marked it Context."
    assert [(a["key"], a["answer"]) for a in said["interview"]["answered"]] == [
        (question["key"], "context")
    ]
    assert phrase_statuses(drafted)[NEVER_DROPS] == "context"
    assert said["draft"] == drafted.get("/api/rubric/draft").json()
    assert "That's just how it looks, nothing to check." in spark.read[0]


def labels(api: TestClient, episode_id: str) -> list[tuple[str, str, str]]:
    found = api.get(f"/api/episodes/{episode_id}/labels").json()
    return [(x["phrase"], x["value"], x["source"]) for x in found]


def test_text_mapped_to_pass_on_a_threshold_question_labels_its_anchor_episode(
    drafted: TestClient, spark: ScriptedText
):
    question = skip_to(drafted, "threshold")
    assert question["phrase"] == NO_PAUSES
    spark.texts.append(mapped("pass"))

    said = say(drafted, "Yeah that's fine, no real pause there.", question["key"])

    assert said["interview"]["answered"][-1]["answer"] == "pass"
    assert labels(drafted, question["episode_id"]) == [(NO_PAUSES, "pass", "interview")]
    assert question["measurement"] in spark.read[0]


def test_text_mapped_to_soft_on_a_hard_or_soft_question_makes_the_criterion_soft(
    drafted: TestClient, spark: ScriptedText
):
    question = skip_to(drafted, "hard_soft")
    spark.texts.append(mapped("soft"))

    said = say(drafted, "Only knock it down a bit, don't throw it out.", question["key"])

    found = next(c for c in said["draft"]["criteria"] if c["id"] == question["criterion_id"])
    assert found["hard"] is False


def test_text_mapped_to_fail_on_a_disagree_question_labels_the_phrase_on_its_episode(
    disagreeing: TestClient, spark: ScriptedText
):
    question = skip_to(disagreeing, "disagree")
    spark.texts.append(mapped("fail"))

    say(disagreeing, "No, three tries is not tidy.", question["key"])

    assert labels(disagreeing, "droid_100:2") == [(TIDY, "fail", "interview")]


def test_text_that_maps_onto_no_answer_changes_nothing_and_says_so(
    drafted: TestClient, spark: ScriptedText
):
    before = interview(drafted)
    spark.texts.append(mapped("none", "I couldn't tell which you meant."))

    said = say(drafted, "Hmm, not sure.", before["question"]["key"])

    assert said["reply"] == "I couldn't tell which you meant."
    assert said["interview"] == before


def test_only_phrase_and_threshold_questions_offer_to_compile_again(
    drafted: TestClient, spark: ScriptedText
):
    question = skip_to(drafted, "hard_soft")
    spark.texts.append(mapped("change"))

    response = drafted.post(
        "/api/interview/text", json={"text": "Rewrite it.", "question_key": question["key"]}
    )

    assert response.status_code == 502, response.text
    assert '"change"' not in spark.read[0]


def others(draft: Any, phrase_text: str) -> list[Any]:
    return [c for c in draft["criteria"] if c["phrase"] != phrase_text]


def test_change_on_a_phrase_question_compiles_only_that_phrase_again_with_the_words(
    drafted: TestClient, spark: ScriptedText
):
    before = drafted.get("/api/rubric/draft").json()
    question = interview(drafted)["question"]
    words = "It means the gripper never lets go before the end: one grasp, held."
    spark.texts.append(mapped("change", "I'll check it as a single held grasp."))
    spark.answers.append(
        {"phrases": [phrase(NEVER_DROPS, criteria=[criterion("grasp_attempts", "<=", 1)])]}
    )

    said = say(drafted, words, question["key"])

    assert said["reply"] == "I'll check it as a single held grasp."
    assert phrase_statuses(drafted)[NEVER_DROPS] == "checked"
    (dropped,) = [c for c in said["draft"]["criteria"] if c["phrase"] == NEVER_DROPS]
    assert dropped["id"] == "grasp-attempts-2"  # an id no Criterion of the draft had
    assert others(said["draft"], NEVER_DROPS) == before["criteria"]
    assert said["draft"]["description"] == DESCRIPTION
    assert [r["text"] for r in said["draft"]["recompiled"]] == [NEVER_DROPS]
    (prompt,) = spark.prompts[-1:]
    assert f"The curator's answer about {json.dumps(NEVER_DROPS)}: {json.dumps(words)}" in prompt[0]
    assert f"- {json.dumps(ONE_GRASP)}" in prompt[0]
    assert f"- {json.dumps(NEVER_DROPS)}" not in prompt[0]
    assert said["interview"]["question"]["key"] != question["key"]  # it isn't asked again


def test_change_on_a_threshold_question_recompiles_its_phrase_and_keeps_other_answers(
    drafted: TestClient, spark: ScriptedText
):
    answer(drafted, "context")  # never drops it
    answer(drafted, "accept")  # smoothly
    answer(drafted, "pass")  # settles the pause threshold
    answer(drafted, "pass")  # one bisection step on the grasp threshold
    question = interview(drafted)["question"]
    assert (question["kind"], question["phrase"]) == ("threshold", ONE_GRASP)
    before = drafted.get("/api/rubric/draft").json()
    grasps = criterion_of(drafted, ONE_GRASP)
    spark.texts.append(mapped("change", "Up to two attempts, then."))
    spark.answers.append(
        {"phrases": [phrase(ONE_GRASP, criteria=[criterion("grasp_attempts", "<=", 2)])]}
    )

    said = say(drafted, "Two tries are fine, three are too many.", question["key"])

    now = criterion_of(drafted, ONE_GRASP)
    assert (now["id"], now["threshold"], now["assumptions"]) == (grasps["id"], 2.0, [])
    assert others(said["draft"], ONE_GRASP) == others(before, ONE_GRASP)
    assert [(a["subject"], a["answer"]) for a in said["interview"]["answered"]] == [
        (NEVER_DROPS, "context"),
        ("smoothly", "accept"),
        (NO_PAUSES, "pass"),
    ]  # the grasp threshold's answer went with its old Criterion
    assert phrase_statuses(drafted)[NEVER_DROPS] == "context"
    assert said["interview"]["question"]["key"] != question["key"]


def test_with_no_question_the_words_edit_the_description_which_recompiles_as_an_edit(
    drafted: TestClient, spark: ScriptedText
):
    answer(drafted, "context")  # never drops it
    before = drafted.get("/api/rubric/draft").json()
    edited = f"{DESCRIPTION} Done within 20 s."
    spark.texts.append({"description": edited, "reply": "Added a 20 s limit."})
    quick = criterion("active_duration_s", "<", 20)
    spark.answers.append({"phrases": [phrase("Done within 20 s", criteria=[quick])]})

    said = say(drafted, "It should also finish within 20 seconds.", None)

    assert said["reply"] == "Added a 20 s limit."
    assert said["draft"]["description"] == edited
    assert said["draft"]["criteria"][: len(before["criteria"])] == before["criteria"]
    assert said["draft"]["criteria"][-1]["phrase"] == "Done within 20 s"
    assert [(a["subject"], a["answer"]) for a in said["interview"]["answered"]] == [
        (NEVER_DROPS, "context")
    ]  # carried, as for any edit
    assert DESCRIPTION in spark.read[-1]
    assert "It should also finish within 20 seconds." in spark.read[-1]
    assert spark.prompts[-1][0].endswith(f"- {json.dumps('Done within 20 s')}")


def test_words_that_ask_no_edit_leave_the_description_and_compile_nothing(
    drafted: TestClient, spark: ScriptedText
):
    before = drafted.get("/api/rubric/draft").json()
    compiles = spark.formats.count("rubric")
    spark.texts.append({"description": f" {DESCRIPTION}\n", "reply": "Nothing to change."})

    said = say(drafted, "Looks good to me.", None)

    assert said["reply"] == "Nothing to change."
    assert said["draft"] == before
    assert spark.formats.count("rubric") == compiles


def test_words_to_a_question_no_longer_asked_are_a_409_with_no_spark_call(
    drafted: TestClient, spark: ScriptedText
):
    calls = len(spark.formats)

    response = drafted.post(
        "/api/interview/text", json={"text": "Leave it.", "question_key": "threshold:gone"}
    )

    assert response.status_code == 409
    assert len(spark.formats) == calls


def test_an_unreadable_reading_of_the_words_is_a_502_that_changes_nothing(
    drafted: TestClient, spark: ScriptedText
):
    before = interview(drafted)
    spark.texts.append("not json")

    response = drafted.post(
        "/api/interview/text", json={"text": "Leave it.", "question_key": before["question"]["key"]}
    )

    assert response.status_code == 502
    assert interview(drafted) == before


def test_answering_in_your_own_words_needs_the_meta_api(settings: Settings):
    with TestClient(create_app(settings)) as no_meta:
        response = no_meta.post("/api/interview/text", json={"text": "Hi.", "question_key": None})

    assert response.status_code == 503
    assert "MODEL_API_KEY" in response.json()["detail"]


def test_with_no_draft_there_is_nothing_to_answer(api: TestClient, spark: ScriptedText):
    response = api.post("/api/interview/text", json={"text": "Hi.", "question_key": None})

    assert response.status_code == 404
    assert spark.read == []


# One answer of each kind that changes something, cycling where a question offers several.
CHANGING = {"phrase": ["context"], "words": ["accept"], "hard_soft": ["soft", "hard"]}


def test_template_answers_never_ask_spark(drafted: TestClient, spark: ScriptedText):
    calls, given = len(spark.formats), 0
    while (question := interview(drafted)["question"]) is not None:
        values = CHANGING.get(question["kind"], ["pass", "fail"])
        answer(drafted, values[given % len(values)])
        given += 1

    answered = {a["answer"] for a in interview(drafted)["answered"]}
    assert {"context", "accept", "pass", "fail", "soft", "hard"} <= answered
    assert len(spark.formats) == calls


def asking_now(api: TestClient) -> AnswerDraw:
    question = interview(api)["question"]
    return AnswerDraw(key=question["key"], episode_id=question.get("episode_id"), answer="accept")


def test_the_question_answered_while_spark_compiles_the_words_is_a_409_that_keeps_it(
    drafted: TestClient, spark: ScriptedText
):
    ctx = app_context(drafted)
    before = drafted.get("/api/rubric/draft").json()
    question = interview(drafted)["question"]
    spark.texts.append(mapped("change"))
    spark.answers.append({"phrases": [phrase(NEVER_DROPS, "context", reason="Flavour.")]})
    draw = asking_now(drafted)
    spark.while_reading = lambda: answer_now(ctx, draw)

    response = drafted.post(
        "/api/interview/text", json={"text": "Just flavour.", "question_key": question["key"]}
    )

    assert response.status_code == 409, response.text
    assert drafted.get("/api/rubric/draft").json()["compiled_at"] == before["compiled_at"]
    assert [a["answer"] for a in interview(drafted)["answered"]] == ["accept"]


def test_a_recompile_while_spark_compiles_the_words_is_a_409_that_keeps_it(
    drafted: TestClient, spark: ScriptedText
):
    ctx = app_context(drafted)
    question = interview(drafted)["question"]
    spark.texts.append(mapped("change"))
    spark.answers.append({"phrases": [phrase(NEVER_DROPS, "context", reason="Flavour.")]})

    def recompiled_meanwhile() -> None:
        draft = ctx.drafts.get()
        assert draft is not None
        ctx.drafts.save(draft.model_copy(update={"compiled_at": "later"}))

    spark.while_reading = recompiled_meanwhile

    response = drafted.post(
        "/api/interview/text", json={"text": "Just flavour.", "question_key": question["key"]}
    )

    assert response.status_code == 409, response.text
    assert drafted.get("/api/rubric/draft").json()["compiled_at"] == "later"
