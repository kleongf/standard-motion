"""The seeded Rubric scores every ingested Episode, served for the Episodes table and the
Workstation."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from tests.conftest import OPEN_GRIPPER_EPISODE
from tests.helpers import app_context, ask_visual, reference_label, track_cleanly, wait_for_job
from winnow.baseline.prompts import FROZEN
from winnow.rubric.models import Rubric
from winnow.rubric.store import RubricStore

FIRST_TRY, NEVER_DROPS, PLACES, NO_PAUSES = FROZEN.phrases
HIGH_RELEASE_EPISODE = 1  # the fixture's i % 3 == 1 release within the release height's margin
REGRASP_EPISODE = 2  # the fixture's failures (i % 3 == 2) are Episode 42-shaped


@pytest.fixture
def ingested(asked_api: TestClient) -> TestClient:
    api = asked_api  # Spark sees every Episode's object placed on its target
    indices = [0, HIGH_RELEASE_EPISODE, REGRASP_EPISODE, OPEN_GRIPPER_EPISODE]
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": indices})
    wait_for_job(api, job.json()["job_id"])
    ask_visual(api)
    for index in indices:  # their outputs show only once labelled
        reference_label(api, f"droid_100:{index}")
    for index in (0, HIGH_RELEASE_EPISODE, REGRASP_EPISODE):
        track_cleanly(api, f"droid_100:{index}")
    return api


def test_the_rubric_is_seeded_from_the_frozen_description(api: TestClient):
    version = api.get("/api/rubric").json()

    assert version["version"] == 1
    rubric = version["rubric"]
    assert rubric["description"] == FROZEN.text
    assert rubric["phrases"] == list(FROZEN.phrases)
    criteria = {c["id"]: c for c in rubric["criteria"]}
    assert {(c["primitive"], c["phrase"], c["kind"]) for c in criteria.values()} == {
        ("grasp_attempts", FIRST_TRY, "measured"),
        ("in_hand_lost_s", NEVER_DROPS, "tracked"),
        ("fall_after_release", NEVER_DROPS, "tracked"),
        ("release_height_m", NEVER_DROPS, "measured"),
        ("final_overlap", PLACES, "tracked"),
        ("ask_video", PLACES, "visual"),
        ("longest_still_s", NO_PAUSES, "measured"),
    }
    attempts = criteria["grasp-attempts"]
    assert (attempts["comparator"], attempts["threshold"], attempts["hard"]) == ("<=", 1, True)
    assert criteria["release-height"]["threshold"] == 0.05
    assert criteria["longest-pause"]["params"] == {"speed_below_m_s": 0.01}
    assert criteria["final-overlap"]["window"] == {"kind": "last_n_s", "seconds": 1.0}
    placed = criteria["placed-on-target"]
    assert (placed["window"]["kind"], placed["crop"], placed["hard"]) == (
        "after_release",
        "placement",
        True,
    )
    assert placed["question"] and len(placed["paraphrases"]) == 2  # frozen
    guessed = [
        c for id_, c in criteria.items() if id_ not in ("grasp-attempts", "placed-on-target")
    ]
    assert all(c["assumptions"] for c in guessed)  # guesses until the interview
    settings = rubric["settings"]
    assert settings["gripper_closed_level"]["value"] == 0.2
    assert settings["grasp_rise_m"]["value"] == 0.02
    assert settings["gripper_closed_level"]["assumption"]  # nobody has confirmed it yet


def test_every_episode_gets_a_triage_decision_and_reason(ingested: TestClient):
    listed = ingested.get("/api/triage").json()

    assert listed["rubric_version"] == 1
    rows = {r["episode_id"]: r for r in listed["rows"]}
    assert {i: r["decision"] for i, r in rows.items()} == {
        "droid_100:0": "keep",
        "droid_100:1": "needs_review",
        "droid_100:2": "reject",
        "droid_100:4": "reject",
    }
    assert rows["droid_100:2"]["reason"] == (
        f'Rejected: "{FIRST_TRY}" failed. 2 failed grasp attempts, at 0.9 s and 1.3 s, '
        "before the grasp at 1.8 s."
    )
    assert "never closed" in rows["droid_100:4"]["reason"]


def test_an_episodes_triage_has_its_criterion_results_with_moments(ingested: TestClient):
    triage = ingested.get(f"/api/episodes/droid_100:{REGRASP_EPISODE}/triage").json()

    assert (triage["episode_id"], triage["rubric_version"]) == ("droid_100:2", 1)
    assert triage["decision"] == "reject"
    result = triage["criteria"][0]
    assert result["status"] == "fail" and result["measurement"] == "3 attempts"
    assert [m["label"] for m in result["moments"]] == ["Attempt 1", "Attempt 2", "Grasp"]
    assert result["at_s"] == result["moments"][0]["t"]
    assert result["window"] == {"start": 0.0, "end": pytest.approx(44 / 15, abs=1e-3)}
    assert [s["t"] for s in triage["reason"] if s["t"] is not None] == [
        m["t"] for m in result["moments"]
    ]
    first_try = triage["phrases"][0]
    assert first_try == {
        "phrase": FIRST_TRY,
        "hard": True,
        "status": "fail",
        "label": None,
        "p_pass": 0.0,
    }
    assert triage["phrases"][1]["status"] == "unsure"  # "never drops it": its high release
    assert (triage["p_keep"], triage["confidence"]) == (0.0, 1.0)


def test_rows_carry_confidence_signals_and_the_phrases_that_didnt_pass(ingested: TestClient):
    rows = {r["episode_id"]: r for r in ingested.get("/api/triage").json()["rows"]}

    high = rows[f"droid_100:{HIGH_RELEASE_EPISODE}"]
    assert high["not_passed"] == [{"phrase": NEVER_DROPS, "status": "unsure"}]
    assert high["uncertainty"] == ["near threshold"]
    assert 0.5 < high["confidence"] < 0.95
    assert high["reason"] == (
        f'Needs review: "{NEVER_DROPS}": near threshold (4.4 cm against ≤ 5 cm).'
    )
    regrasp = rows[f"droid_100:{REGRASP_EPISODE}"]
    # Like Episode 42 it also releases high (6.3 cm): an unconfirmed fail behind the Reject.
    assert regrasp["not_passed"] == [
        {"phrase": FIRST_TRY, "status": "fail"},
        {"phrase": NEVER_DROPS, "status": "unsure"},
    ]
    assert regrasp["uncertainty"] == ["unconfirmed fail"]
    assert regrasp["confidence"] == 1.0


def test_an_unknown_episode_has_no_triage(api: TestClient):
    assert api.get("/api/episodes/droid_100:9/triage").status_code == 404


def test_rubric_versions_are_immutable_and_the_latest_one_scores(ingested: TestClient):
    rubrics = app_context(ingested).rubrics
    seeded = rubrics.latest()
    stricter = seeded.rubric.model_copy(deep=True)
    stricter.criteria[0].threshold = 3
    stricter.criteria = stricter.criteria[:1]

    added = rubrics.add(Rubric.model_validate(stricter.model_dump()))

    assert added.version == 2
    assert rubrics.get(1) == seeded
    rows = {r["episode_id"]: r for r in ingested.get("/api/triage").json()["rows"]}
    assert rows["droid_100:2"]["decision"] == "keep"
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        ingested_db = app_context(ingested).db
        ingested_db.execute("UPDATE rubric_versions SET rubric = '{}' WHERE version = 1")


def test_an_older_seed_gives_way_to_the_current_one_until_a_rubric_is_run(api: TestClient):
    ctx = app_context(api)
    seeded = ctx.rubrics.latest()
    older = seeded.rubric.model_copy(update={"criteria": seeded.rubric.criteria[:1]})

    reseeded = RubricStore(ctx.db, older)  # a seed from another build of the app

    assert reseeded.latest().version == 2 and reseeded.latest().rubric == older
    assert RubricStore(ctx.db, older).latest().version == 2  # same seed: no new version
    run = reseeded.add(seeded.rubric)
    assert RubricStore(ctx.db, older).latest() == run  # a Run Rubric is never replaced
