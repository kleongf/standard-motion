from fastapi.testclient import TestClient

from tests.helpers import wait_for_job
from tests.tracking.boxing import BOX, EXTERIOR_2, save_box
from tests.tracking.scripted_sam import SAMPLE_BOX, ScriptedSam


def tracks_of(api: TestClient, episode_id: str) -> dict[str, dict[str, object]]:
    return {t["kind"]: t for t in api.get(f"/api/episodes/{episode_id}/tracks").json()}


def test_saving_a_box_tracks_the_object_from_it_in_the_chosen_view(
    scripted_api: TestClient, sam: ScriptedSam
):
    job = save_box(scripted_api, "droid_100:1")

    assert {i["step"] for i in job["items"]} == {"track_exterior", "target_box"}  # type: ignore[union-attr]
    assert job["failed"] == 0
    [call] = sam.made("000001/exterior_image_2_left.5fps.mp4")
    assert call.prompt == "<0f>1<|box;x1=100;y1=60;x2=139;y2=89;w=320;h=180|>"
    track = tracks_of(scripted_api, "droid_100:1")["exterior"]
    assert (track["camera"], track["status"], track["seed_frame"]) == (EXTERIOR_2, "tracked", 0)
    assert (track["fps"], track["frames"]) == (5, 15)
    boxes = track["boxes"]
    assert isinstance(boxes, list) and len(boxes) == 15  # pyright: ignore[reportUnknownArgumentType]
    first = boxes[0]  # pyright: ignore[reportUnknownVariableType]
    assert (first["left"], first["top"], first["right"], first["bottom"]) == SAMPLE_BOX
    assert track["health"] == {
        "area_jumps": [],
        "centre_jumps": [],
        "missing_fraction": 0.0,
        "lost": False,
    }
    assert scripted_api.get("/api/dataset").json()["exterior_tracks"] == 1


def test_an_episode_with_no_box_gets_no_exterior_track_or_target_box(
    scripted_api: TestClient, sam: ScriptedSam
):
    save_box(scripted_api, "droid_100:1")

    assert "exterior" not in tracks_of(scripted_api, "droid_100:0")
    assert [t["episode_id"] for t in scripted_api.get("/api/target-boxes").json()] == [
        "droid_100:1"
    ]
    assert sam.made("000000/exterior_image_1_left.5fps.mp4") == []


def test_redrawing_the_box_tracks_again_from_the_new_one(
    scripted_api: TestClient, sam: ScriptedSam
):
    save_box(scripted_api, "droid_100:1")
    save_box(scripted_api, "droid_100:1", camera="exterior_image_1_left")

    assert tracks_of(scripted_api, "droid_100:1")["exterior"]["camera"] == "exterior_image_1_left"
    assert len(sam.made("exterior_image_1_left.5fps.mp4")) == 1


def test_without_meta_a_box_is_saved_and_nothing_is_queued(api: TestClient):
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [1]})
    wait_for_job(api, job.json()["job_id"])

    assert api.put("/api/episodes/droid_100:1/box", json=BOX).status_code == 200
    assert api.get("/api/jobs/latest", params={"kind": "box"}).json() is None
    assert api.get("/api/dataset").json()["exterior_tracks"] is None
