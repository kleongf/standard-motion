from collections.abc import Iterator

import numpy as np
import pytest
from fastapi.testclient import TestClient

from standard_motion.app import create_app
from standard_motion.core.settings import Settings
from standard_motion.episodes.models import EpisodeSignals
from standard_motion.tracking.wrist import seed_frame, wrist_prompt
from tests.conftest import OPEN_GRIPPER_EPISODE
from tests.helpers import wait_for_job
from tests.record_meta import RECORDINGS


@pytest.fixture
def replay_api(settings: Settings) -> Iterator[TestClient]:
    """The app with Meta served from the recorded fixture replies: no network, no key."""
    replayed = settings.model_copy(update={"meta_replay": RECORDINGS})
    with TestClient(create_app(replayed)) as client:
        yield client


def ingest(api: TestClient, *indices: int) -> dict[str, object]:
    response = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": indices})
    return wait_for_job(api, response.json()["job_id"])


def test_ingest_tracks_the_object_in_the_wrist_view(replay_api: TestClient):
    job = ingest(replay_api, 0)

    assert job["failed"] == 0
    [track] = replay_api.get("/api/episodes/droid_100:0/tracks").json()
    assert (track["kind"], track["camera"], track["status"]) == (
        "wrist",
        "wrist_image_left",
        "tracked",
    )
    assert (track["fps"], track["frames"], track["width"], track["height"]) == (5, 15, 320, 180)
    assert track["seed_frame"] == 5  # closes at 15 Hz frame 14; +3 is frame 17, 5 fps frame 5
    boxes = track["boxes"]
    assert len(boxes) == 15
    assert boxes[-1]["left"] - boxes[0]["left"] > 50  # the fixture's block slides right
    assert not track["health"]["lost"]
    assert replay_api.get("/api/dataset").json()["wrist_tracks"] == 1


def test_an_episode_whose_gripper_never_closes_gets_no_wrist_track_and_that_is_recorded(
    replay_api: TestClient,
):
    job = ingest(replay_api, OPEN_GRIPPER_EPISODE)

    wrist = next(i for i in job["items"] if i["step"] == "track_wrist")  # type: ignore[union-attr]
    assert (wrist["status"], wrist["detail"]) == (
        "done",
        "the gripper never closed: no wrist track",
    )
    [track] = replay_api.get(f"/api/episodes/droid_100:{OPEN_GRIPPER_EPISODE}/tracks").json()
    assert (track["status"], track["boxes"], track["health"]) == ("no_closure", [], None)
    status = replay_api.get("/api/dataset").json()
    assert (status["wrist_tracks"], status["wrist_no_closure"]) == (0, 1)


def test_without_a_meta_api_key_there_is_no_wrist_track(api: TestClient):
    ingest(api, 0)

    assert api.get("/api/episodes/droid_100:0/tracks").json() == []
    assert api.get("/api/dataset").json()["wrist_tracks"] is None


def test_an_unknown_episode_has_no_tracks(api: TestClient):
    assert api.get("/api/episodes/droid_100:99/tracks").status_code == 404


def signals(gripper: list[float]) -> EpisodeSignals:
    n = len(gripper)
    return EpisodeSignals(
        episode_index=0,
        fps=15.0,
        timestamps=np.arange(n) / 15.0,
        position=np.zeros((n, 3)),
        gripper=np.asarray(gripper, dtype=np.float64),
        dataset_outcome=None,
    )


def test_the_seed_is_three_robot_frames_after_the_first_closure_on_the_5_fps_clip():
    gripper = [0.0] * 30 + [1.0] * 10 + [0.0] * 10 + [1.0] * 40  # a failed grasp, then the hold

    assert seed_frame(signals(gripper), sam_frames=30) == 11  # frame 33 at 15 Hz


def test_the_seed_counts_closed_from_a_gripper_past_0_3():
    gripper = [0.0] * 30 + [0.25] * 6 + [0.35] * 20  # barely closing until frame 36

    assert seed_frame(signals(gripper), sam_frames=20) == 13  # frame 39 at 15 Hz


def test_the_seed_stays_on_the_clip_and_needs_a_closure():
    assert seed_frame(signals([0.0] * 44 + [1.0]), sam_frames=15) == 14
    assert seed_frame(signals([0.0] * 45), sam_frames=15) is None


def test_the_prompt_is_the_object_point_and_three_finger_negatives_scaled_to_the_frame():
    assert wrist_prompt(5, (320, 180)) == (
        "<5f>1<|point;x=190;y=105;w=320;h=180|>"
        "-<|point;x=120;y=150;w=320;h=180|>"
        "-<|point;x=260;y=150;w=320;h=180|>"
        "-<|point;x=190;y=172;w=320;h=180|>"
    )
    assert "<|point;x=380;y=210;w=640;h=360|>" in wrist_prompt(5, (640, 360))
