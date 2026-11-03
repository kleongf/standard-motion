"""The Audit sample: a seeded sample of auto-Keeps (and auto-Rejects) drawn once per Rubric
version from the Episodes outside the Test set, each marked Good or Bad with `audit` labels that
measure Keep precision and never change a Triage decision."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from standard_motion.baseline.prompts import FROZEN
from standard_motion.rubric.models import Rubric
from tests.conftest import OPEN_GRIPPER_EPISODE
from tests.helpers import app_context, ask_visual, reference_label, track_cleanly, wait_for_job

KEEP, NEEDS_REVIEW, REJECT = "droid_100:0", "droid_100:1", "droid_100:2"
NO_GRASP = f"droid_100:{OPEN_GRIPPER_EPISODE}"  # rejected too: its gripper never closes
_, NEVER_DROPS, _, _ = FROZEN.phrases
INDICES = [0, 1, 2, OPEN_GRIPPER_EPISODE]


@pytest.fixture
def ingested(asked_api: TestClient) -> TestClient:
    api = asked_api  # Spark sees every Episode's object placed on its target
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": INDICES})
    wait_for_job(api, job.json()["job_id"])
    ask_visual(api)
    for index in INDICES:
        track_cleanly(api, f"droid_100:{index}")  # tracked Criteria pass; robot data decides
        reference_label(api, f"droid_100:{index}")
    return api


def audit(api: TestClient) -> Any:
    return api.get("/api/audit").json()


def draw(api: TestClient, seed: int | None = 7) -> Any:
    drawn = api.post("/api/audit/sample", json={} if seed is None else {"seed": seed})
    assert drawn.status_code == 200, drawn.text
    return drawn.json()


def label(api: TestClient, episode_id: str, phrase: str, value: str, source: str = "audit"):
    saved = api.post(
        f"/api/episodes/{episode_id}/labels",
        json={"phrase": phrase, "value": value, "source": source},
    )
    assert saved.status_code == 201, saved.text


def mark_good(api: TestClient, episode_id: str) -> None:
    for phrase in FROZEN.phrases:
        label(api, episode_id, phrase, "pass")


def decision(api: TestClient, episode_id: str) -> str:
    return api.get(f"/api/episodes/{episode_id}/triage").json()["decision"]


def test_nothing_is_drawn_until_asked(ingested: TestClient):
    sample = audit(ingested)

    assert (sample["rubric_version"], sample["seed"], sample["items"]) == (1, None, [])
    assert sample["phrases"] == list(FROZEN.phrases)
    assert sample["precision"]["good"] == {"count": 0, "of": 0, "low": None, "high": None}


def test_drawing_samples_the_auto_keeps_and_rejects_and_records_the_seed(ingested: TestClient):
    sample = draw(ingested, seed=7)

    assert sample["seed"] == 7 and sample["drawn_at"]
    assert [(i["episode_id"], i["kind"], i["mark"]) for i in sample["items"]] == [
        (KEEP, "keep", None),
        (REJECT, "reject", None),
        (NO_GRASP, "reject", None),
    ]
    assert audit(ingested) == sample


def test_the_sample_is_drawn_once_per_rubric_version(ingested: TestClient):
    first = draw(ingested, seed=7)
    label(ingested, NEEDS_REVIEW, NEVER_DROPS, "pass", source="review")  # now kept, by a human

    again = draw(ingested, seed=8)

    assert again == first
    rubrics = app_context(ingested).rubrics
    rubrics.add(Rubric.model_validate(rubrics.latest().rubric.model_dump()))
    assert (audit(ingested)["rubric_version"], audit(ingested)["seed"]) == (2, None)
    redrawn = draw(ingested, seed=8)
    # A Keep a human label decided isn't Standard Motion's own, so it isn't audited.
    assert [i["episode_id"] for i in redrawn["items"]] == [KEEP, REJECT, NO_GRASP]


def test_test_set_episodes_are_never_sampled(ingested: TestClient):
    app_context(ingested).sets.add("test", [REJECT])

    assert [i["episode_id"] for i in draw(ingested)["items"]] == [KEEP, NO_GRASP]


def test_with_no_auto_keep_outside_the_test_set_there_is_nothing_to_draw(ingested: TestClient):
    app_context(ingested).sets.add("test", [KEEP])

    refused = ingested.post("/api/audit/sample", json={})

    assert refused.status_code == 409
    assert "auto-Keep" in refused.json()["detail"]
    assert audit(ingested)["seed"] is None


def test_without_a_seed_one_is_chosen_and_recorded(ingested: TestClient):
    sample = draw(ingested, seed=None)

    assert isinstance(sample["seed"], int)
    assert audit(ingested)["seed"] == sample["seed"]


def test_marking_good_then_bad_updates_keep_precision(ingested: TestClient):
    draw(ingested)
    mark_good(ingested, KEEP)

    good = audit(ingested)
    assert good["items"][0]["mark"] == "good" and good["items"][0]["failed"] == []
    assert good["precision"]["good"]["count"] == 1 and good["precision"]["good"]["of"] == 1
    assert good["precision"]["lower_bound"] == pytest.approx(0.1)  # 1 of 1 at 90%
    assert good["precision"]["lower_bound_confidence"] == 0.9

    label(ingested, KEEP, NEVER_DROPS, "fail")

    bad = audit(ingested)
    assert bad["items"][0]["mark"] == "bad" and bad["items"][0]["failed"] == [NEVER_DROPS]
    assert (bad["precision"]["good"]["count"], bad["precision"]["good"]["of"]) == (0, 1)
    assert bad["precision"]["lower_bound"] is None


def test_a_partly_marked_or_reject_item_does_not_count_toward_keep_precision(
    ingested: TestClient,
):
    draw(ingested)
    label(ingested, KEEP, NEVER_DROPS, "pass")  # one Phrase of four: not yet Good
    mark_good(ingested, REJECT)

    sample = audit(ingested)

    assert [i["mark"] for i in sample["items"]] == [None, "good", None]
    assert sample["precision"]["good"]["of"] == 0


def test_an_audit_label_never_changes_a_triage_decision(ingested: TestClient):
    draw(ingested)
    label(ingested, KEEP, NEVER_DROPS, "fail")
    label(ingested, NEEDS_REVIEW, NEVER_DROPS, "pass")

    assert decision(ingested, KEEP) == "keep"
    assert decision(ingested, NEEDS_REVIEW) == "needs_review"
    triage = ingested.get(f"/api/episodes/{KEEP}/triage").json()
    assert all(p["label"] is None for p in triage["phrases"])


def test_an_audit_label_does_not_supersede_a_review_label_on_the_same_phrase(
    ingested: TestClient,
):
    label(ingested, NEEDS_REVIEW, NEVER_DROPS, "pass", source="review")
    label(ingested, NEEDS_REVIEW, NEVER_DROPS, "fail")

    assert decision(ingested, NEEDS_REVIEW) == "keep"


def test_audit_labels_given_on_an_older_rubric_version_do_not_mark_the_new_sample(
    ingested: TestClient,
):
    draw(ingested)
    mark_good(ingested, KEEP)
    rubrics = app_context(ingested).rubrics
    rubrics.add(Rubric.model_validate(rubrics.latest().rubric.model_dump()))

    assert [i["mark"] for i in draw(ingested)["items"]] == [None, None, None]


def test_a_sample_is_drawn_at_the_versions_s_and_again_once_calibration_changes_it(
    ingested: TestClient,
):
    first = draw(ingested, seed=7)
    mark_good(ingested, KEEP)
    assert (first["s"], first["earlier_s"]) == (1.0, None)

    # Calibrated narrower, Episode 1's release height (0.0437 against ≤ 0.05) is no longer
    # within its margin, so Standard Motion keeps it too: the old sample no longer shows its Keeps.
    app_context(ingested).calibrations.add(1, 0.5, 12, 0, True, False)
    stale = audit(ingested)
    assert (stale["s"], stale["seed"], stale["items"], stale["earlier_s"]) == (0.5, None, [], 1.0)
    assert decision(ingested, NEEDS_REVIEW) == "keep"

    fresh = draw(ingested, seed=8)

    assert (fresh["s"], fresh["seed"], fresh["earlier_s"]) == (0.5, 8, None)
    assert [(i["episode_id"], i["kind"], i["mark"]) for i in fresh["items"]] == [
        (KEEP, "keep", "good"),  # picked again: its mark, given on this version, carries over
        (NEEDS_REVIEW, "keep", None),
        (REJECT, "reject", None),
        (NO_GRASP, "reject", None),
    ]
    assert fresh["precision"]["good"]["count"] == 1


def test_a_keep_counts_toward_precision_only_while_it_is_still_a_keep(ingested: TestClient):
    draw(ingested)
    mark_good(ingested, KEEP)
    assert audit(ingested)["precision"]["good"]["of"] == 1

    label(ingested, KEEP, NEVER_DROPS, "fail", source="review")  # a reviewer rejects it

    sample = audit(ingested)
    assert (sample["items"][0]["kind"], sample["items"][0]["decision"]) == ("keep", "reject")
    assert sample["precision"]["good"]["of"] == 0  # no longer one of Standard Motion's Keeps


def test_marked_rejects_count_the_good_episodes_rejected(ingested: TestClient):
    draw(ingested)
    mark_good(ingested, REJECT)
    label(ingested, NO_GRASP, NEVER_DROPS, "fail")

    sample = audit(ingested)

    assert [i["decision"] for i in sample["items"]] == ["keep", "reject", "reject"]
    assert (sample["good_rejects"]["count"], sample["good_rejects"]["of"]) == (1, 2)
    assert sample["precision"]["good"]["of"] == 0
