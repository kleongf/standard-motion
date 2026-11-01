"""The Describe interview through its API: which question code asks next, what each answer
changes in the Rubric draft, the labels answers leave, and undo."""

from fastapi.testclient import TestClient

from tests.interview.client import (
    DESCRIPTION,
    NEVER_DROPS,
    NO_PAUSES,
    ONE_GRASP,
    answer,
    compile_answer,
    criterion_of,
    interview,
    pauses_phrase,
    phrase_statuses,
    recompile,
)
from tests.rubric.scripted import ScriptedCompile, phrase


def test_phrases_come_first_in_description_order_then_thresholds_by_anchor_episodes_near(
    drafted: TestClient,
):
    asked: list[tuple[str, str]] = []
    for value in ("accept", "accept", "skip", "skip"):
        question = interview(drafted)["question"]
        asked.append((question["kind"], question.get("text") or question["phrase"]))
        answer(drafted, value)

    assert asked == [
        ("phrase", NEVER_DROPS),  # Unsupported
        ("words", "smoothly"),  # in no Phrase
        # Every anchor Episode sits near the pause threshold, none near the grasp one.
        ("threshold", NO_PAUSES),
        ("threshold", ONE_GRASP),
    ]
    assert interview(drafted)["question"]["kind"] == "hard_soft"  # then hard or soft


def to_grasp_threshold(api: TestClient) -> None:
    """Past the Phrase questions, and the pause threshold skipped."""
    for value in ("accept", "accept", "skip"):
        answer(api, value)


def test_a_bisection_card_brackets_the_threshold_and_labels_each_episode_it_asks(
    drafted: TestClient,
):
    to_grasp_threshold(drafted)

    first = interview(drafted)["question"]
    # Episodes 0 and 1 make 1 attempt, Episode 2 makes 3; the assumed threshold is ≤ 1.
    assert (first["episode_id"], first["measurement"], first["prompt"]) == (
        "droid_100:0",
        "1 attempt",
        f"Is 1 attempt fine for “{ONE_GRASP}”?",
    )
    assert [o["label"] for o in first["options"]][:2] == [
        f"Fine: “{ONE_GRASP}” passes",
        f"Not fine: “{ONE_GRASP}” fails",
    ]
    answer(drafted, "pass")
    assert interview(drafted)["question"]["episode_id"] == "droid_100:2"
    after = answer(drafted, "fail")

    grasps = criterion_of(drafted, ONE_GRASP)
    assert (grasps["threshold"], grasps["margin"], grasps["assumptions"]) == (2.0, 2.0, [])
    settled = after["answered"][-1]
    assert settled["changed_criterion"] == grasps["id"]
    assert settled["effect"].endswith("Threshold 1 → 2, margin ± 2.")
    labels = drafted.get("/api/episodes/droid_100:2/labels").json()
    assert [(x["phrase"], x["value"], x["source"], x["rubric_version"]) for x in labels] == [
        (ONE_GRASP, "fail", "interview", None)
    ]


def test_undo_restores_the_previous_threshold_and_withdraws_the_label(drafted: TestClient):
    to_grasp_threshold(drafted)
    answer(drafted, "pass")
    first_id = answer(drafted, "fail")["answered"][-2]["id"]  # Episode 0's answer

    response = drafted.delete(f"/api/interview/answers/{first_id}")

    assert response.status_code == 200, response.text
    grasps = criterion_of(drafted, ONE_GRASP)
    assert (grasps["threshold"], grasps["margin"]) == (1.0, 0.0)
    assert grasps["assumptions"] == ["One attempt is the most."]
    # Both of its answers are undone, so it asks about Episode 0 again.
    assert response.json()["question"]["episode_id"] == "droid_100:0"
    for episode_id in ("droid_100:0", "droid_100:2"):
        labels = drafted.get(f"/api/episodes/{episode_id}/labels").json()
        assert [x["withdrawn_at"] is not None for x in labels] == [True]
    triage = drafted.get("/api/episodes/droid_100:2/triage").json()
    assert all(p["label"] is None for p in triage["phrases"])


def test_answers_that_agree_with_the_threshold_confirm_it(drafted: TestClient):
    for value in ("accept", "accept"):
        answer(drafted, value)
    pauses = interview(drafted)["question"]
    assert pauses["phrase"] == NO_PAUSES

    # Every anchor Episode pauses 0 s, so one fine answer leaves nothing to bracket.
    after = answer(drafted, "pass")

    assert criterion_of(drafted, NO_PAUSES)["assumptions"] == []
    assert criterion_of(drafted, NO_PAUSES)["threshold"] == 0.1
    assert after["answered"][-1]["resolution"] == "confirmed"


def test_marking_phrases_context_covers_them_and_undo_puts_them_back(drafted: TestClient):
    assert interview(drafted)["covered"] is False
    unsupported = answer(drafted, "context")["answered"][-1]
    after = answer(drafted, "context")  # "smoothly", in no Phrase

    assert phrase_statuses(drafted)[NEVER_DROPS] == "context"
    assert phrase_statuses(drafted)["smoothly"] == "context"
    assert drafted.get("/api/rubric/draft").json()["uncovered"] == []
    assert (after["covered"], after["phrases_left"]) == (True, 0)
    assert after["question"]["kind"] == "threshold"  # thresholds can still be asked

    undone = drafted.delete(f"/api/interview/answers/{unsupported['id']}").json()

    assert phrase_statuses(drafted)[NEVER_DROPS] == "unsupported"
    assert phrase_statuses(drafted)["smoothly"] == "context"  # the later answer stands
    assert undone["covered"] is False
    assert undone["question"]["text"] == NEVER_DROPS


def test_an_answer_to_a_question_not_being_asked_is_refused(drafted: TestClient):
    body = {"key": "threshold:grasp-attempts", "episode_id": "droid_100:0", "answer": "pass"}

    assert drafted.post("/api/interview/answers", json=body).status_code == 409
    assert interview(drafted)["answered"] == []


def test_compiling_afresh_starts_a_new_interview(drafted: TestClient, spark: ScriptedCompile):
    answer(drafted, "context")
    spark.answers.append(compile_answer())

    drafted.post("/api/rubric/draft/compile", json={"description": DESCRIPTION})

    assert interview(drafted)["answered"] == []
    assert interview(drafted)["question"]["text"] == NEVER_DROPS


def test_answers_on_phrases_an_edit_left_alone_survive_it_and_can_be_undone(
    drafted: TestClient, spark: ScriptedCompile
):
    answer(drafted, "accept")  # "never drops it" stays unchecked
    answer(drafted, "context")  # "smoothly" checks nothing
    answer(drafted, "skip")  # the pause threshold
    answer(drafted, "pass")
    answer(drafted, "fail")  # the grasp threshold settles at 2
    before = interview(drafted)["answered"]
    edited = DESCRIPTION.replace("Tidy pick", "Careful tidy pick")  # moves everything after it
    careful = phrase("Careful tidy pick", "context", reason="Names the task.")

    recompile(drafted, spark, edited, careful)

    after = interview(drafted)
    assert [(a["kind"], a["subject"], a["answer"]) for a in after["answered"]] == [
        (a["kind"], a["subject"], a["answer"]) for a in before
    ]
    assert (after["question"]["kind"], after["covered"]) == ("hard_soft", True)
    assert criterion_of(drafted, ONE_GRASP)["threshold"] == 2.0
    by_subject = {a["subject"]: a for a in after["answered"]}

    undone = drafted.delete(f"/api/interview/answers/{by_subject['smoothly']['id']}").json()
    assert undone["question"]["text"] == "smoothly"
    assert phrase_statuses(drafted).get("smoothly") is None  # in no Phrase again
    first_grasp = next(a for a in after["answered"] if a["subject"] == ONE_GRASP)
    drafted.delete(f"/api/interview/answers/{first_grasp['id']}")
    assert criterion_of(drafted, ONE_GRASP)["threshold"] == 1.0
    undone = drafted.delete(f"/api/interview/answers/{by_subject[NEVER_DROPS]['id']}").json()
    assert undone["question"]["text"] == NEVER_DROPS


def test_a_question_on_an_edited_phrase_is_asked_again(drafted: TestClient, spark: ScriptedCompile):
    answer(drafted, "accept")  # "never drops it"
    answer(drafted, "accept")  # "smoothly"
    answer(drafted, "skip")  # the pause threshold
    at_all = "no pauses at all"

    recompile(drafted, spark, DESCRIPTION.replace(NO_PAUSES, at_all), pauses_phrase(at_all))

    after = interview(drafted)
    assert [a["subject"] for a in after["answered"]] == [NEVER_DROPS, "smoothly"]
    assert after["question"]["phrase"] == at_all


def test_there_is_no_interview_before_a_compile(api: TestClient):
    assert api.get("/api/interview").status_code == 404


def test_an_answer_re_sorts_the_anchor_pool_and_an_unbracketed_threshold_stays_assumed(
    drafted: TestClient,
):
    def rejected() -> list[str]:
        preview = drafted.post("/api/rubric/draft/preview", json={}).json()
        return [e["episode_id"] for e in preview["episodes"] if e["decision"] == "reject"]

    to_grasp_threshold(drafted)
    assert rejected() == ["droid_100:2"]  # 3 grasp attempts
    answer(drafted, "pass")  # Episode 0's 1 attempt

    after = answer(drafted, "pass")  # Episode 2's 3 attempts too: nothing past it to bracket

    assert after["answered"][-1]["resolution"] == "unbracketed"
    assert criterion_of(drafted, ONE_GRASP)["assumptions"] == ["One attempt is the most."]
    assert rejected() == []  # its label overrides the Phrase's fail


def test_undo_keeps_direct_edits_made_since_to_what_the_answer_did_not_change(
    drafted: TestClient,
):
    to_grasp_threshold(drafted)
    answer(drafted, "pass")
    settled = answer(drafted, "fail")["answered"][-1]
    grasps = criterion_of(drafted, ONE_GRASP)["id"]
    drafted.patch("/api/rubric/draft", json={"criteria": {grasps: {"hard": False}}})

    drafted.delete(f"/api/interview/answers/{settled['id']}")

    after = criterion_of(drafted, ONE_GRASP)
    assert (after["threshold"], after["hard"]) == (1.0, False)
