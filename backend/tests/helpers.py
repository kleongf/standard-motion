import subprocess
import time
from pathlib import Path
from typing import cast

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient
from numpy.typing import NDArray

from standard_motion.baseline.prompts import FROZEN
from standard_motion.boxes.models import BoxDraw
from standard_motion.core.context import AppContext
from standard_motion.episodes.clips import probe
from standard_motion.tracking.models import FrameBox, TargetBox, Track, TrackBox, TrackKind


def wait_for_job(api: TestClient, job_id: int, timeout_s: float = 60.0) -> dict[str, object]:
    """Poll a job until no item is queued or running, and return its final state."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        job: dict[str, object] = api.get(f"/api/jobs/{job_id}").json()
        if job["finished"]:
            return job
        time.sleep(0.05)
    raise TimeoutError(f"Job {job_id} still running after {timeout_s} s")


def ask_visual(api: TestClient, *episode_ids: str) -> dict[str, object]:
    """Ask the latest Rubric's visual Criteria (of every Episode by default) and wait."""
    body = {"episode_ids": list(episode_ids)} if episode_ids else {}
    started = api.post("/api/visual/ask", json=body)
    assert started.status_code == 202, started.text
    return wait_for_job(api, started.json()["job_id"])


def app_context(api: TestClient) -> AppContext:
    """The context the running app built, to read stores no route exposes."""
    app = cast(FastAPI, api.app)
    return cast(AppContext, app.state.context)


def track_cleanly(api: TestClient, episode_id: str) -> None:
    """Store what boxing a fixture Episode would make, with no SAM: a hand-drawn box, an exterior
    track of the object resting inside a hand-drawn target box, and a wrist track of it between
    the fingers throughout. The seeded Rubric's tracked Criteria all pass on these."""
    ctx = app_context(api)
    camera = "exterior_image_2_left"
    ctx.boxes.save(episode_id, BoxDraw(camera=camera, x1=145, y1=85, x2=175, y2=115), (320, 180))
    resting = [TrackBox(frame=f, left=145, top=85, right=175, bottom=115) for f in range(15)]
    held = [TrackBox(frame=f, left=170, top=85, right=210, bottom=125) for f in range(15)]
    tracks: list[tuple[TrackKind, str, list[TrackBox]]] = [
        ("exterior", camera, resting),
        ("wrist", "wrist_image_left", held),
    ]
    for kind, view, boxes in tracks:
        ctx.tracks.save(
            Track(
                episode_id=episode_id,
                kind=kind,
                camera=view,
                status="tracked",
                fps=5,
                frames=15,
                width=320,
                height=180,
                seed_frame=0,
                boxes=boxes,
                health=None,
            )
        )
    ctx.targets.save(
        TargetBox(
            episode_id=episode_id,
            camera=camera,
            origin="hand",
            status="found",
            target="pot",
            box=FrameBox(left=120, top=60, right=200, bottom=140),
            frame_width=320,
            frame_height=180,
            made_at="2026-10-30T00:00:00+00:00",
        )
    )


def rgb(clip: Path) -> NDArray[np.uint8]:
    """A clip's decoded frames as (frames, height, width, 3)."""
    frames, width, height = probe(clip)
    out = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(clip), "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-"],
        check=True, capture_output=True,
    ).stdout  # fmt: skip
    return np.frombuffer(out, np.uint8).reshape(frames, height, width, 3)


def reference_label(api: TestClient, episode_id: str) -> None:
    """Give an Episode a first-pass Reference label passing every Phrase, which reveals its
    outputs. The instruction is used only where the Episode has none."""
    phrases = [{"phrase": p, "passed": True, "interval": None} for p in FROZEN.phrases]
    body = {"phrases": phrases, "elapsed_s": 10.0, "instruction": "Put the block in the bowl"}
    saved = api.post(f"/api/episodes/{episode_id}/reference-labels", json=body)
    assert saved.status_code == 201, saved.text


def decoded(clip: Path | str) -> list[str]:
    """Each decoded frame's checksum, in order."""
    out = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(clip), "-f", "framemd5", "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [line.rsplit(",", 1)[1].strip() for line in out.splitlines() if not line.startswith("#")]
