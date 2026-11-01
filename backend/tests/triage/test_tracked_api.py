"""The seeded Rubric's tracked Criteria, scored from each Episode's stored tracks and target box."""

from fastapi.testclient import TestClient

from tests.helpers import reference_label, wait_for_job
from tests.tracking.boxing import EXTERIOR_2, save_box
from winnow.baseline.prompts import FROZEN

_, NEVER_DROPS, PLACES, _ = FROZEN.phrases
KEPT_EPISODE = "droid_100:0"  # grasps first time, releases low, never pauses


def results_by_id(triage: dict[str, object]) -> dict[str, dict[str, object]]:
    criteria: list[dict[str, object]] = triage["criteria"]  # type: ignore[assignment]
    return {str(r["criterion_id"]): r for r in criteria}


def test_an_episode_with_no_hand_drawn_box_has_unsure_placement_and_needs_review(
    api: TestClient,
):
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [0]})
    wait_for_job(api, job.json()["job_id"])
    reference_label(api, KEPT_EPISODE)

    triage = api.get(f"/api/episodes/{KEPT_EPISODE}/triage").json()

    results = results_by_id(triage)
    for placement in ("final-overlap", "fall-after-release"):
        result = results[placement]
        assert (result["status"], result["uncertainty"]) == ("unsure", "source missing")
        assert "box the object on Prepare" in "".join(s["text"] for s in result["evidence"])  # type: ignore[union-attr]
    assert triage["decision"] == "needs_review"
    assert f'"{PLACES}": source missing' in triage["reason"][0]["text"]


def test_a_boxed_episode_is_scored_from_its_exterior_track_and_target_box(
    scripted_api: TestClient,
):
    # Scripted SAM follows the box on every frame and finds the "pot" target in the same place.
    save_box(scripted_api, KEPT_EPISODE)
    reference_label(scripted_api, KEPT_EPISODE)

    triage = scripted_api.get(f"/api/episodes/{KEPT_EPISODE}/triage").json()

    results = results_by_id(triage)
    overlap, fall = results["final-overlap"], results["fall-after-release"]
    assert (overlap["status"], overlap["value"], overlap["camera"]) == ("pass", 1.0, EXTERIOR_2)
    assert (fall["status"], fall["value"]) == ("pass", 0.0)
    assert overlap["track_plot"]["label"] == "Share inside the target box"  # type: ignore[index]
    assert results["in-hand-lost"]["phrase"] == NEVER_DROPS
