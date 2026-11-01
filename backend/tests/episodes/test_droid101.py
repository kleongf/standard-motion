import json
import subprocess
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from tests.helpers import app_context, wait_for_job
from winnow.core.settings import Settings


def frames(clip: Path) -> int:
    out = subprocess.run(
        [
            *("ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0"),
            *("-show_entries", "stream=nb_read_frames", "-of", "json", str(clip)),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return int(json.loads(out.stdout)["streams"][0]["nb_read_frames"])


def test_a_droid101_episode_ingests_into_the_same_shape_with_joints_and_extrinsics(
    api: TestClient, settings: Settings
):
    job = api.post("/api/episodes/ingest", json={"source": "droid_1.0.1", "indices": [2]})
    wait_for_job(api, job.json()["job_id"])

    [episode] = api.get("/api/episodes").json()
    assert episode["id"] == "droid_1.0.1:2"
    assert episode["instruction"] == "Move the cup to the left"
    stored = app_context(api).episodes.get(episode["id"])
    assert (
        stored is not None and stored.dataset_outcome is False
    )  # hidden by the API until labelled
    assert episode["frames"] == 36
    assert episode["cameras"] == [
        "exterior_image_1_left",
        "exterior_image_2_left",
        "wrist_image_left",
    ]
    folder = settings.data_dir / "episodes" / "droid_1.0.1" / "000002"
    assert frames(folder / "wrist_image_left.mp4") == 36  # its own stretch of the shared video

    ctx = app_context(api)
    stored = ctx.episodes.get("droid_1.0.1:2")
    assert stored is not None
    signals = ctx.episodes.load_signals(stored)
    joints, extrinsics = signals.joint_positions, signals.camera_extrinsics
    assert joints is not None and joints.shape == (36, 7)
    assert extrinsics is not None
    assert np.allclose(extrinsics["exterior_image_2_left"][0], [0.5, 0.1, 0.4, 0, 0.5, 1.5])
    assert api.get("/api/episodes/droid_1.0.1:2/signals").json()["gripper"][0] == 0.0
