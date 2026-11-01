import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import CORRUPT_EPISODE
from tests.helpers import app_context, wait_for_job
from winnow.core.settings import Settings


def ingest(api: TestClient, *indices: int) -> dict[str, object]:
    response = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": indices})
    assert response.status_code == 202
    return wait_for_job(api, response.json()["job_id"])


def probe(clip: Path) -> dict[str, str]:
    out = subprocess.run(
        [
            *("ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries"),
            *("stream=codec_name,r_frame_rate", "-of", "json", str(clip)),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(out.stdout)["streams"][0]


def test_ingested_episodes_are_listed_with_their_instruction_and_outcome(api: TestClient):
    job = ingest(api, 0, 1, 2)

    assert job["done"] == 3 and job["failed"] == 0
    episodes = {e["id"]: e for e in api.get("/api/episodes").json()}
    assert sorted(episodes) == ["droid_100:0", "droid_100:1", "droid_100:2"]
    assert episodes["droid_100:1"]["instruction"] == "Move the black remote control to the left"
    assert episodes["droid_100:2"]["instruction"] is None  # blank in the source
    # The API hides the Dataset outcome until a Reference label; ingest still keeps it.
    stored = app_context(api).episodes.get("droid_100:2")
    assert stored is not None and stored.dataset_outcome is False
    assert episodes["droid_100:0"]["frames"] == 45
    assert episodes["droid_100:0"]["duration_s"] == 3.0


def test_ingest_writes_h264_clips_and_5_fps_clips_for_every_camera(
    api: TestClient, settings: Settings
):
    ingest(api, 0)

    folder = settings.data_dir / "episodes" / "droid_100" / "000000"
    for camera in ("exterior_image_1_left", "exterior_image_2_left", "wrist_image_left"):
        assert probe(folder / f"{camera}.mp4") == {"codec_name": "h264", "r_frame_rate": "15/1"}
        assert probe(folder / f"{camera}.5fps.mp4") == {"codec_name": "h264", "r_frame_rate": "5/1"}


def test_ingesting_the_same_episodes_again_does_no_new_work(api: TestClient, settings: Settings):
    ingest(api, 0)
    clip = settings.data_dir / "episodes" / "droid_100" / "000000" / "wrist_image_left.mp4"
    written = clip.stat().st_mtime_ns

    again = ingest(api, 0)

    assert again["items"] == [
        {
            "position": 0,
            "step": "ingest",
            "label": "droid_100:0",
            "status": "done",
            "detail": "already ingested",
        }
    ]
    assert clip.stat().st_mtime_ns == written


def test_an_episode_with_unreadable_video_fails_alone(api: TestClient):
    job = ingest(api, 0, CORRUPT_EPISODE, 1)

    assert (job["done"], job["failed"]) == (2, 1)
    failed = [i for i in job["items"] if i["status"] == "failed"]  # type: ignore[union-attr]
    assert failed[0]["label"] == f"droid_100:{CORRUPT_EPISODE}"
    assert "ffmpeg failed" in failed[0]["detail"]
    assert [e["id"] for e in api.get("/api/episodes").json()] == ["droid_100:0", "droid_100:1"]


def test_an_unknown_source_is_refused(api: TestClient):
    response = api.post("/api/episodes/ingest", json={"source": "robofac", "indices": [1]})

    assert response.status_code == 422


def test_two_jobs_ingesting_the_same_episode_at_once_both_succeed(api: TestClient):
    first = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [1]})
    second = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [1]})

    jobs = [wait_for_job(api, r.json()["job_id"]) for r in (first, second)]

    assert [j["done"] for j in jobs] == [1, 1]
    details = sorted(str(j["items"][0]["detail"]) for j in jobs)  # type: ignore[index]
    assert details == ["None", "already ingested"]
