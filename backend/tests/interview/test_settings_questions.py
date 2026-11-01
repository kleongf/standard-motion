"""The interview's later questions through its API: after the Phrases and thresholds, whether
each Criterion is hard or soft, then the two grasp settings, bisected on anchor Episodes."""

from typing import Any

from fastapi.testclient import TestClient

from tests.interview.client import (
    DESCRIPTION,
    NO_PAUSES,
    ONE_GRASP,
    answer,
    criterion_of,
    interview,
    pauses_phrase,
    recompile,
    skip_to,
)
from tests.rubric.scripted import ScriptedCompile


def test_after_the_thresholds_it_asks_hard_or_soft_per_criterion_then_each_setting(
    drafted: TestClient,
):
    asked: list[str] = []
    while (question := interview(drafted)["question"]) is not None:
        asked.append(question["kind"])
        answer(drafted, "accept" if question["kind"] in ("phrase", "words") else "skip")

    assert asked == [
        "phrase",
        "words",
        "threshold",
        "threshold",
        "hard_soft",
        "hard_soft",
        "setting",
        "setting",
    ]


def test_a_hard_soft_answer_sets_hard_and_undo_puts_back_only_that(drafted: TestClient):
    question = skip_to(drafted, "hard_soft")
    assert question["prompt"] == (
        "If an Episode fails “Grasp attempts, up to and including the grasp, ≤ 1”, should it be "
        "rejected outright, or only lower its quality?"
    )

    after = answer(drafted, "soft")

    grasps = criterion_of(drafted, ONE_GRASP)
    assert grasps["hard"] is False
    soft = after["answered"][-1]
    assert (soft["subject"], soft["effect"], soft["changed_criterion"], soft["label_id"]) == (
        question["english"],
        "Soft: failing it only lowers the Episode's quality.",
        grasps["id"],
        None,  # it judges no Episode
    )
    assert after["question"]["criterion_id"] != grasps["id"]  # asked once per Criterion
    drafted.patch("/api/rubric/draft", json={"criteria": {grasps["id"]: {"threshold": 3}}})

    undone = drafted.delete(f"/api/interview/answers/{soft['id']}").json()

    grasps = criterion_of(drafted, ONE_GRASP)
    assert (grasps["hard"], grasps["threshold"]) == (True, 3.0)  # the direct edit stands
    assert undone["question"]["key"] == question["key"]


def settings(api: TestClient) -> Any:
    return api.get("/api/rubric/draft").json()["settings"]


def test_a_closed_answer_the_level_already_sorts_right_confirms_it(drafted: TestClient):
    question = skip_to(drafted, "setting")
    # Every fixture closure closes fully, so each anchor Episode's peak is 1.
    assert (question["setting"], question["prompt"], question["measurement"]) == (
        "gripper_closed_level",
        "Is the gripper closed at this moment?",
        "closed to 1.00",
    )
    assert [o["label"] for o in question["options"]][:2] == ["Closed", "Open"]

    after = answer(drafted, "pass")

    assert settings(drafted)["gripper_closed_level"] == {
        "value": 0.2,
        "margin": 0.1,
        "assumption": None,
    }
    assert after["answered"][-1]["effect"] == (
        f"Marked {question['episode_id']} closed. Gripper closed level confirmed at 0.2."
    )
    assert after["question"]["setting"] == "grasp_rise_m"


def test_answers_either_side_of_the_grasp_rise_set_it_and_undo_puts_the_assumption_back(
    drafted: TestClient,
):
    skip_to(drafted, "setting")
    answer(drafted, "skip")  # the closed level
    # Episode 2's failed attempts rise 0 cm; 0 and 1 lift their grasps well over 2 cm.
    first = interview(drafted)["question"]
    assert (first["episode_id"], first["measurement"]) == ("droid_100:2", "rose 0.0 cm")
    answer(drafted, "fail")
    second = interview(drafted)["question"]
    assert second["episode_id"] in ("droid_100:0", "droid_100:1")
    assert second["asked"] == 1

    after = answer(drafted, "pass")

    rise = settings(drafted)["grasp_rise_m"]
    assert rise == {
        "value": round(second["value"] / 2, 6),
        "margin": round(second["value"], 6),
        "assumption": None,
    }
    assert (after["answered"][-1]["resolution"], after["question"]) == ("set", None)
    assert all(a["label_id"] is None for a in after["answered"])

    drafted.delete(f"/api/interview/answers/{after['answered'][-2]['id']}")

    assert settings(drafted)["grasp_rise_m"]["value"] == 0.02
    assert settings(drafted)["grasp_rise_m"]["assumption"] is not None
    assert interview(drafted)["question"]["episode_id"] == "droid_100:2"


def test_a_recompile_carries_answers_on_kept_criteria_and_on_the_settings(
    drafted: TestClient, spark: ScriptedCompile
):
    skip_to(drafted, "hard_soft")
    answer(drafted, "soft")  # the grasp Criterion
    answer(drafted, "soft")  # the pause one
    answer(drafted, "pass")  # the closed level, confirmed
    at_all = "no pauses at all"

    recompile(drafted, spark, DESCRIPTION.replace(NO_PAUSES, at_all), pauses_phrase(at_all))

    after = interview(drafted)
    kinds = [(a["kind"], a["answer"]) for a in after["answered"]]
    assert kinds == [
        ("phrase", "accept"),
        ("words", "accept"),
        ("threshold", "skip"),  # the grasp one; the pause one was on the edited Phrase
        ("hard_soft", "soft"),  # the grasp one, kept
        ("setting", "pass"),
    ]
    assert after["question"]["phrase"] == at_all  # its threshold is asked again
    assert settings(drafted)["gripper_closed_level"]["assumption"] is None
    soft = next(a for a in after["answered"] if a["kind"] == "hard_soft")
    drafted.delete(f"/api/interview/answers/{soft['id']}")
    assert criterion_of(drafted, ONE_GRASP)["hard"] is True
