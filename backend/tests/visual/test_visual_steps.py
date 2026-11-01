"""The crop and visual steps through the API: asking the latest Rubric's visual Criteria cuts one
clip per Criterion and Episode and asks Spark each frozen prompt about it."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import app_context, ask_visual, reference_label, track_cleanly, wait_for_job
from tests.tracking.boxing import EXTERIOR_2, save_box
from tests.tracking.scripted_sam import SAMPLE_BOX
from tests.visual.scripted import ScriptedVisual
from winnow.baseline.prompts import FROZEN
from winnow.core.settings import Settings
from winnow.rubric.models import DraftPhrase, RubricDraft

_, _, PLACES, _ = FROZEN.phrases
KEPT = "droid_100:0"  # the fixture's i % 3 == 0: one clean grasp, released low


@pytest.fixture
def spark(visual_spark: ScriptedVisual) -> ScriptedVisual:
    return visual_spark


@pytest.fixture
def app_api(asked_api: TestClient) -> TestClient:
    return asked_api


def ingest(api: TestClient, *indices: int) -> None:
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": indices})
    wait_for_job(api, job.json()["job_id"])
    for index in indices:
        reference_label(api, f"droid_100:{index}")


def ask(api: TestClient) -> dict[str, Any]:
    return ask_visual(api)


def placement(api: TestClient, episode_id: str = KEPT) -> dict[str, Any]:
    triage = api.get(f"/api/episodes/{episode_id}/triage").json()
    return next(c for c in triage["criteria"] if c["kind"] == "visual")


def test_the_seeded_placement_question_is_asked_three_times_on_one_clip(
    app_api: TestClient, spark: ScriptedVisual
):
    ingest(app_api, 0)

    job = ask(app_api)

    assert [(i["step"], i["status"]) for i in job["items"]] == [
        ("crop", "done"),
        ("visual", "done"),
    ]
    assert len(spark.calls) == 3
    assert len({c.clip for c in spark.calls}) == 1  # one clip, three prompts
    assert all("Put the marker in the pot" in c.prompt for c in spark.calls)
    result = placement(app_api)
    assert (result["phrase"], result["status"], result["hard"]) == (PLACES, "pass", True)
    track_cleanly(app_api, KEPT)  # its tracked Criteria pass too (answers don't depend on boxes)
    triage = app_api.get(f"/api/episodes/{KEPT}/triage").json()
    assert triage["decision"] == "keep"


def test_the_evidence_shows_each_samples_answer_and_serves_the_clip(
    app_api: TestClient, spark: ScriptedVisual
):
    spark.answers["000000"] = ("pass", "fail", "pass")
    ingest(app_api, 0)
    ask(app_api)

    result = placement(app_api)

    assert (result["status"], result["uncertainty"]) == ("unsure", "samples split")
    samples = result["visual"]["samples"]
    assert sorted(s["reply"]["answer"] for s in samples) == ["fail", "pass", "pass"]
    assert all(s["reply"]["observation"].startswith("The marker rests") for s in samples)
    clip = result["visual"]["clip"]
    assert clip["camera"] == "exterior_image_1_left"
    assert 0 < clip["start"] < clip["end"] <= 3.0
    served = app_api.get(f"/api/episodes/{KEPT}/visual-clips/{clip['name']}")
    assert served.status_code == 200
    assert served.headers["content-type"] == "video/mp4"


def test_asking_again_is_all_cache_hits(app_api: TestClient, spark: ScriptedVisual):
    ingest(app_api, 0)
    ask(app_api)

    again = ask(app_api)

    assert [i["status"] for i in again["items"]] == ["done", "done"]
    assert len(spark.calls) == 3  # every Spark call was a cache hit
    assert again["items"][0]["detail"] == "clip already cut"


def test_without_the_meta_api_nothing_is_asked(api: TestClient):
    response = api.post("/api/visual/ask", json={})

    assert response.status_code == 503
    assert "MODEL_API_KEY" in response.json()["detail"]


def test_placement_crops_to_the_objects_final_box_joined_with_the_target_box(
    app_api: TestClient,
):
    ingest(app_api, 0)
    save_box(app_api, KEPT)  # SAM tracks the object, and finds the pot, in exterior 2

    ask(app_api)

    clip = placement(app_api)["visual"]["clip"]
    assert clip["camera"] == EXTERIOR_2
    left, top, right, bottom = SAMPLE_BOX  # both the final object box and the target box
    box = clip["box"]
    assert box["left"] <= left and box["top"] <= top
    assert box["right"] >= right and box["bottom"] >= bottom
    assert (box["right"] - box["left"]) * (box["bottom"] - box["top"]) < 320 * 180 / 4
    assert placement(app_api)["camera"] == EXTERIOR_2  # the Workstation shows the clip's view


def test_a_crop_that_fails_leaves_the_criterion_unsure_with_its_error(
    app_api: TestClient, settings: Settings
):
    ingest(app_api, 0)
    clip = settings.data_dir / "episodes" / "droid_100" / "000000" / "exterior_image_1_left.mp4"
    clip.unlink()

    job = ask(app_api)

    assert [i["status"] for i in job["items"]] == ["failed", "failed"]
    result = placement(app_api)
    assert (result["status"], result["uncertainty"]) == ("unsure", "step failed")
    assert "crop" in result["evidence"][0]["text"]


def draft_of_the_seed(api: TestClient) -> None:
    """A draft with the seeded Rubric's Phrases and Criteria, as compile might have made it."""
    seeded = api.get("/api/rubric").json()["rubric"]
    description: str = seeded["description"]
    phrases = [
        DraftPhrase(
            text=p,
            start=description.index(p),
            end=description.index(p) + len(p),
            restatement=p,
            status="checked",
        )
        for p in seeded["phrases"]
    ]
    draft = RubricDraft(
        description=description,
        phrases=phrases,
        settings=seeded["settings"],
        criteria=seeded["criteria"],
        compiled_at="2026-10-29T12:00:00+00:00",
    )
    app_context(api).drafts.save(draft)


def test_run_never_asks_spark_and_reuses_the_answers_to_an_unchanged_question(
    app_api: TestClient, spark: ScriptedVisual
):
    ingest(app_api, 0)
    asked = ask(app_api)  # the seeded version's placement question
    track_cleanly(app_api, KEPT)
    draft_of_the_seed(app_api)

    run = app_api.post("/api/rubric/draft/run")

    assert run.status_code == 201
    latest = app_api.get("/api/jobs/latest", params={"kind": "visual"}).json()
    assert latest["id"] == asked["id"]  # Run queued no visual job: Spark is asked only on request
    assert len(spark.calls) == 3
    triage = app_api.get(f"/api/episodes/{KEPT}/triage").json()
    assert (triage["rubric_version"], triage["decision"]) == (2, "keep")


def test_a_sample_spark_answers_unsure_sends_the_episode_to_review(
    app_api: TestClient, spark: ScriptedVisual
):
    spark.answers["000000"] = ("pass", "unsure", "pass")
    ingest(app_api, 0)
    ask(app_api)

    triage = app_api.get(f"/api/episodes/{KEPT}/triage").json()

    assert triage["decision"] == "needs_review"
    assert "Spark said unsure" in "".join(s["text"] for s in triage["reason"])


def test_two_criteria_with_one_window_and_view_share_one_clip(
    app_api: TestClient, spark: ScriptedVisual
):
    ingest(app_api, 0)
    draft_of_the_seed(app_api)
    draft = app_context(app_api).drafts.get()
    assert draft is not None
    placed = next(c for c in draft.criteria if c.kind == "visual")
    upright = placed.model_copy(update={"id": "upright", "question": "Is the object upright?"})
    app_context(app_api).drafts.save(
        draft.model_copy(update={"criteria": [*draft.criteria, upright]})
    )
    app_api.post("/api/rubric/draft/run")

    job = ask(app_api)

    assert [i["status"] for i in job["items"]] == ["done"] * 4  # cut at once, neither fails
    assert len(spark.calls) == 4  # the paraphrases they share are Meta cache hits
    assert len({c.clip for c in spark.calls}) == 1
