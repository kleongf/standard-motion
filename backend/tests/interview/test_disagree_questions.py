"""The interview's last questions through its API: on an anchor Episode where a Phrase's Criteria
disagree, does the Phrase pass? The answer is an interview label on that (Episode, Phrase)."""

from typing import Any

from fastapi.testclient import TestClient

from tests.interview.client import (
    TIDY,
    TIDY_DESCRIPTION,
    answer,
    interview,
    recompile,
    skip_to,
)
from tests.rubric.scripted import ScriptedCompile, criterion, phrase


def labels(api: TestClient, episode_id: str) -> list[Any]:
    return api.get(f"/api/episodes/{episode_id}/labels").json()


def test_where_a_phrases_criteria_disagree_it_asks_last_whether_the_phrase_passes(
    disagreeing: TestClient,
):
    question = skip_to(disagreeing, "disagree")

    assert (question["phrase"], question["episode_id"]) == (TIDY, "droid_100:2")
    assert [(r["status"], r["measurement"]) for r in question["results"]] == [
        ("fail", "3 attempts"),
        ("pass", "0.0 s"),
    ]
    assert [o["answer"] for o in question["options"]] == ["pass", "fail", "skip"]
    assert interview(disagreeing)["disagree_left"] == 1


def test_a_fail_answer_labels_the_episode_on_the_phrase_and_undo_withdraws_it(
    disagreeing: TestClient,
):
    skip_to(disagreeing, "disagree")

    after = answer(disagreeing, "fail")

    answered = after["answered"][-1]
    assert (answered["kind"], answered["subject"], answered["episode_id"]) == (
        "disagree",
        TIDY,
        "droid_100:2",
    )
    assert answered["effect"] == f"Labelled droid_100:2 fail on “{TIDY}”."
    assert (after["question"], after["disagree_left"]) == (None, 0)  # one question per Phrase
    assert [(x["phrase"], x["value"], x["source"]) for x in labels(disagreeing, "droid_100:2")] == [
        (TIDY, "fail", "interview")
    ]

    undone = disagreeing.delete(f"/api/interview/answers/{answered['id']}").json()

    assert labels(disagreeing, "droid_100:2")[0]["withdrawn_at"] is not None
    assert undone["question"]["kind"] == "disagree"


def rejected(api: TestClient) -> list[str]:
    preview = api.post("/api/rubric/draft/preview", json={}).json()
    return [e["episode_id"] for e in preview["episodes"] if e["decision"] == "reject"]


def test_a_pass_answer_overrides_the_phrases_fail_on_that_episode(disagreeing: TestClient):
    skip_to(disagreeing, "disagree")
    assert rejected(disagreeing) == ["droid_100:2"]  # its 3 grasp attempts

    answer(disagreeing, "pass")

    assert rejected(disagreeing) == []


def test_an_episode_already_labelled_on_the_phrase_is_not_asked_about(disagreeing: TestClient):
    skip_to(disagreeing, "threshold")
    answer(disagreeing, "pass")  # Episode 0's 1 grasp attempt
    # Episode 2's 3 attempts too: nothing past it brackets the threshold, so it still fails.
    assert answer(disagreeing, "pass")["answered"][-1]["resolution"] == "unbracketed"

    after = skip_to(disagreeing, None)

    assert after is None
    assert interview(disagreeing)["disagree_left"] == 0


def test_it_asks_once_per_phrase_on_the_episode_its_criteria_disagree_most(
    api: TestClient, spark: ScriptedCompile
):
    # No anchor Episode releases below -1 m, but release height alone can't confirm a fail: it
    # is unconfirmed on all three, beside Episodes 0 and 1's passing grasp, Episode 2's failing.
    grasps = criterion("grasp_attempts", "<=", 1)
    low = criterion("release_height_m", "<=", -1)
    spark.answers.append({"phrases": [phrase(TIDY, criteria=[grasps, low])]})
    api.post("/api/rubric/draft/compile", json={"description": TIDY})
    question = skip_to(api, "disagree")
    assert question["prompt"] == (
        f"A fail on “{TIDY}” can't be confirmed on this Episode. Does it pass?"
    )
    assert [r["unconfirmed"] for r in question["results"]] == [False, True]

    after = answer(api, "skip")

    assert after["answered"][-1]["effect"] == "Skipped: its Criteria decide."
    assert (after["question"], after["disagree_left"]) == (None, 0)


def test_a_recompile_carries_the_answer_on_a_phrase_it_left_alone(
    disagreeing: TestClient, spark: ScriptedCompile
):
    skip_to(disagreeing, "disagree")
    answer(disagreeing, "fail")
    edited = TIDY_DESCRIPTION.replace("A tidy pick", "A careful tidy pick")  # moves the Phrase

    recompile(
        disagreeing, spark, edited, phrase("A careful tidy pick", "context", reason="Names it.")
    )

    after = interview(disagreeing)
    carried = after["answered"][-1]
    assert (carried["kind"], carried["key"]) == ("disagree", f"disagree:{edited.index(TIDY)}")
    assert after["question"] is None
    disagreeing.delete(f"/api/interview/answers/{carried['id']}")
    assert labels(disagreeing, "droid_100:2")[0]["withdrawn_at"] is not None
    assert interview(disagreeing)["question"]["key"] == carried["key"]


def test_a_crisp_fail_beside_a_crisp_pass_is_asked_before_an_unconfirmed_fail(
    api: TestClient, spark: ScriptedCompile
):
    # Release height's fail is unconfirmed on every anchor Episode; only on Episode 2 does a
    # crisp grasp fail sit beside the crisp pause pass too.
    grasps = criterion("grasp_attempts", "<=", 1)
    pauses = criterion("longest_still_s", "<", 5, params={"speed_below_m_s": 0.01})
    low = criterion("release_height_m", "<=", -1)
    spark.answers.append({"phrases": [phrase(TIDY, criteria=[grasps, pauses, low])]})
    api.post("/api/rubric/draft/compile", json={"description": TIDY})

    question = skip_to(api, "disagree")

    assert question["episode_id"] == "droid_100:2"
    assert question["prompt"] == f"Its Criteria disagree on this Episode. Does “{TIDY}” pass?"
    assert question["measurement"] == "2 fail, 1 passes"
