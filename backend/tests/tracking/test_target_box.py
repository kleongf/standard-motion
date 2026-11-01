from typing import cast

from fastapi.testclient import TestClient

from tests.helpers import app_context, wait_for_job
from tests.tracking.boxing import BOX, EXTERIOR_2, save_box
from tests.tracking.scripted_sam import SAMPLE_BOX, ScriptedSam
from winnow.tracking.target import chosen_target_box

# Fixture instructions: Episode 0 "Put the marker in the pot", Episode 1 "Move the black remote
# control to the left" (a direction, no target), Episode 2 none.
HAND = {"x1": 200, "y1": 20, "x2": 300, "y2": 120}


def target_of(api: TestClient, episode_id: str) -> dict[str, object] | None:
    targets = api.get("/api/target-boxes").json()
    return next((t for t in targets if t["episode_id"] == episode_id), None)


def step_item(job: dict[str, object], step: str) -> dict[str, object]:
    items = cast(list[dict[str, object]], job["items"])
    return next(i for i in items if i["step"] == step)


def edges(target: dict[str, object] | None) -> tuple[object, ...]:
    assert target is not None
    box = cast(dict[str, object], target["box"])
    return tuple(box[k] for k in ("left", "top", "right", "bottom"))


def test_sam_finds_the_instructions_target_on_frame_zero_of_the_boxed_view(
    scripted_api: TestClient, sam: ScriptedSam
):
    save_box(scripted_api, "droid_100:0")

    [call] = sam.made("000000/exterior_image_2_left.frame0.mp4")  # one frame: no track
    assert call.prompt == "pot"
    target = target_of(scripted_api, "droid_100:0")
    assert target is not None
    assert {k: target[k] for k in ("camera", "origin", "status", "target")} == {
        "camera": EXTERIOR_2,
        "origin": "sam",
        "status": "found",
        "target": "pot",
    }
    assert edges(target) == SAMPLE_BOX
    status = scripted_api.get("/api/dataset").json()
    assert (status["target_boxes"], status["targets_missing"]) == (1, 0)


def test_a_target_sam_cannot_find_is_recorded_not_failed(
    scripted_api: TestClient, sam: ScriptedSam
):
    sam.visible.clear()
    job = save_box(scripted_api, "droid_100:0")

    assert step_item(job, "target_box")["status"] == "done"
    assert step_item(job, "target_box")["detail"] == "SAM found no pot"
    target = target_of(scripted_api, "droid_100:0")
    assert target is not None and (target["status"], target["box"]) == ("not_found", None)
    status = scripted_api.get("/api/dataset").json()
    assert (status["target_boxes"], status["targets_missing"]) == (0, 1)


def test_a_missing_instruction_means_no_target_prompt_and_that_is_recorded(
    scripted_api: TestClient, sam: ScriptedSam
):
    job = save_box(scripted_api, "droid_100:2")

    item = step_item(job, "target_box")
    assert (item["status"], item["detail"]) == ("done", "no instruction: no target prompt")
    assert sam.made("frame0.mp4") == []
    target = target_of(scripted_api, "droid_100:2")
    assert target is not None
    assert (target["status"], target["target"], target["box"]) == ("no_instruction", None, None)


def test_an_instruction_naming_no_place_means_no_target_prompt(
    scripted_api: TestClient, sam: ScriptedSam
):
    job = save_box(scripted_api, "droid_100:1")

    assert step_item(job, "target_box")["detail"] == "the instruction names no target"
    assert sam.made("frame0.mp4") == []
    target = target_of(scripted_api, "droid_100:1")
    assert target is not None and target["status"] == "no_target"


def test_a_hand_drawn_target_box_replaces_sams_and_is_what_scoring_reads(
    scripted_api: TestClient,
):
    save_box(scripted_api, "droid_100:0")

    drawn = scripted_api.put("/api/episodes/droid_100:0/target-box", json=HAND)
    save_box(scripted_api, "droid_100:0")  # SAM answering again never overrides the curator

    assert drawn.status_code == 200
    target = target_of(scripted_api, "droid_100:0")
    assert target is not None
    assert (target["origin"], target["status"], target["camera"]) == ("hand", "found", EXTERIOR_2)
    assert edges(target) == (200, 20, 300, 120)
    ctx = app_context(scripted_api)
    box = ctx.boxes.get("droid_100:0")
    assert box is not None
    chosen = chosen_target_box(ctx.targets, box)
    assert chosen is not None and chosen.origin == "hand"


def test_a_hand_drawn_target_box_fills_in_where_sam_found_none(
    scripted_api: TestClient, sam: ScriptedSam
):
    sam.visible.clear()
    save_box(scripted_api, "droid_100:0")
    scripted_api.put("/api/episodes/droid_100:0/target-box", json=HAND)

    status = scripted_api.get("/api/dataset").json()
    assert (status["target_boxes"], status["targets_missing"]) == (1, 0)


def test_boxing_the_object_in_another_view_drops_a_target_drawn_on_the_old_one(
    scripted_api: TestClient,
):
    save_box(scripted_api, "droid_100:0")
    scripted_api.put("/api/episodes/droid_100:0/target-box", json=HAND)

    save_box(scripted_api, "droid_100:0", camera="exterior_image_1_left")

    target = target_of(scripted_api, "droid_100:0")
    assert target is not None
    assert (target["origin"], target["camera"]) == ("sam", "exterior_image_1_left")


def test_a_target_box_needs_the_object_box_first_and_must_fit_its_frame(
    scripted_api: TestClient,
):
    assert scripted_api.put("/api/episodes/droid_100:0/target-box", json=HAND).status_code == 409
    save_box(scripted_api, "droid_100:0")
    off_frame = HAND | {"x2": 330}
    put = scripted_api.put("/api/episodes/droid_100:0/target-box", json=off_frame)
    assert put.status_code == 422
    assert target_of(scripted_api, "droid_100:0")["origin"] == "sam"  # type: ignore[index]


def test_without_meta_a_target_box_can_still_be_drawn(api: TestClient):
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [0]})
    wait_for_job(api, job.json()["job_id"])
    api.put("/api/episodes/droid_100:0/box", json=BOX)

    assert api.put("/api/episodes/droid_100:0/target-box", json=HAND).status_code == 200
    target = target_of(api, "droid_100:0")
    assert target is not None and (target["origin"], target["target"]) == ("hand", "pot")
    assert api.get("/api/dataset").json()["target_boxes"] == 1


def test_an_instruction_the_labeller_writes_prompts_the_target_box_again(
    scripted_api: TestClient, sam: ScriptedSam
):
    save_box(scripted_api, "droid_100:2")
    phrases = scripted_api.get("/api/reference-labels/description").json()["phrases"]
    label = {
        "phrases": [{"phrase": p, "passed": True, "interval": None} for p in phrases],
        "elapsed_s": 30.0,
        "instruction": "Put the marker in the pot",
    }

    assert scripted_api.post("/api/episodes/droid_100:2/reference-labels", json=label).is_success
    job = scripted_api.get("/api/jobs/latest", params={"kind": "box"}).json()
    wait_for_job(scripted_api, job["id"])

    [call] = sam.made("000002/exterior_image_2_left.frame0.mp4")
    assert call.prompt == "pot"
    target = target_of(scripted_api, "droid_100:2")
    assert target is not None and (target["status"], target["target"]) == ("found", "pot")
