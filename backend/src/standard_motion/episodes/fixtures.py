"""Synthetic droid_100-layout Episodes for tests and e2e, so neither depends on the Hub.

Writes the same files the droid_100 adapter reads (the v3.0 parquet and tasks on `main`, one mp4
per Episode per camera on `v2.0`), with a simple pick-and-place motion: reach, close, lift,
carry, release. The wrist view shows a red block sliding right, under the wrist track's seed
point once the gripper has closed, so SAM has something to follow. Deterministic, so recorded
Meta responses stay valid.
"""

import subprocess
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from standard_motion.episodes.droid100 import CAMERAS, FPS

INSTRUCTIONS = ("Put the marker in the pot", "Move the black remote control to the left", "")


def failed(index: int) -> bool:
    """Every third Episode failed: its Dataset outcome says so, and it took two failed grasp
    attempts before the grasp."""
    return index % 3 == 2


def carry_climb(index: int) -> float:
    """How fast the arm climbs while carrying, in m per Episode length. Episodes with
    i % 3 == 1 climb faster, so they release 4.4 cm (i % 6 == 1) or 5.3 cm (i % 6 == 4) above
    where they picked up: inside the seeded release height's margin (5 cm ± 1 cm), so each
    needs review, the 5.3 cm ones with less confidence. Robot data only: recorded Meta replies
    still hold."""
    return 0.17 + 0.01 * (index % 6) if index % 3 == 1 else 0.10


def sliding_block(index: int) -> str:
    """A red block sliding right over grey, under the wrist seed point (190,105) at about 1 s.
    Its start shifts a little per Episode, right through five Episodes and then down, so it
    stays under the seed point and no two Episodes share a clip."""
    return (
        f"color=c=0x5a6470:size=320x180:rate={FPS:g}[bg];"
        f"color=c=0xd03030:size=60x40:rate={FPS:g}[fg];"
        f"[bg][fg]overlay=x='{110 + 4 * (index % 5)}+40*t':y={85 + 2 * (index // 5)}"
    )


def state(
    frames: int, closes: bool = True, regrasps: bool = False, climb: float = 0.10
) -> np.ndarray:
    """End-effector xyz + roll/pitch/yaw + gripper per frame (droid_100's `observation.state`).

    One closure while carrying by default. With `regrasps`, Episode 42's shape: two closures at
    the object's height that lift nothing, then the grasp that lifts it. The first closure starts
    on the same frame either way, so the wrist track's seed (and its recording) doesn't move.
    """
    t = np.linspace(0.0, 1.0, frames)
    x = 0.4 + 0.2 * t
    z = 0.25 - 0.15 * np.sin(np.pi * np.clip(t * 2, 0, 1))  # dip to the object, then lift
    z = np.where(t > 0.5, 0.10 + climb * (t - 0.5), z)
    closed = (t > 0.3) & (t < 0.8)  # closed while carrying
    if regrasps:
        z = np.where(t < 0.3, 0.25 - 0.5 * t, np.where(t < 0.65, 0.10, 0.10 + 0.25 * (t - 0.65)))
        closed = ((t > 0.3) & (t < 0.4)) | ((t > 0.45) & (t < 0.55)) | ((t > 0.6) & (t < 0.9))
    gripper = (closed & closes).astype(np.float64)
    state = np.zeros((frames, 7))
    state[:, 0], state[:, 1], state[:, 2], state[:, 6] = x, 0.0, z, gripper
    return state


def _write_parquet(root: Path, episodes: int, frames: int, open_gripper: tuple[int, ...]) -> None:
    states = [
        state(frames, closes=i not in open_gripper, regrasps=failed(i), climb=carry_climb(i))
        for i in range(episodes)
    ]
    rows = episodes * frames
    episode_index = np.repeat(np.arange(episodes), frames)
    frame_index = np.tile(np.arange(frames), episodes)
    reward = np.zeros(rows)
    reward[frames - 1 :: frames] = [0.0 if failed(i) else 1.0 for i in range(episodes)]
    table = pa.table(  # pyright: ignore[reportUnknownMemberType]
        {
            "observation.state": [list(map(float, r)) for s in states for r in s],
            "timestamp": (frame_index / FPS).astype(np.float32),
            "episode_index": episode_index,
            "frame_index": frame_index,
            "next.reward": reward.astype(np.float32),
            "task_index": np.array([i % len(INSTRUCTIONS) for i in episode_index]),
        }
    )
    data = root / "main" / "data" / "chunk-000"
    data.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, data / "file-000.parquet")  # pyright: ignore[reportUnknownMemberType]
    tasks = pa.table(  # pyright: ignore[reportUnknownMemberType]
        {"task_index": list(range(len(INSTRUCTIONS))), "__index_level_0__": list(INSTRUCTIONS)}
    )
    meta = root / "main" / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    pq.write_table(tasks, meta / "tasks.parquet")  # pyright: ignore[reportUnknownMemberType]


def write_clip(path: Path, frames: int, pattern: str, *options: str) -> None:
    """`pattern` is a lavfi test source's name, or a whole lavfi graph; `options` are more of
    x264's."""
    path.parent.mkdir(parents=True, exist_ok=True)
    source = pattern if "=" in pattern else f"{pattern}=size=320x180:rate={FPS:g}"
    subprocess.run(
        [
            *("ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", source),
            *("-frames:v", str(frames), "-c:v", "libx264", "-pix_fmt", "yuv420p", *options),
            *("-bitexact", "-map_metadata", "-1", str(path)),
        ],
        check=True,
    )


def clip_path(root: Path, index: int, camera: str) -> Path:
    name = f"episode_{index:06d}.mp4"
    return root / "v2.0" / "videos" / "chunk-000" / f"observation.images.{camera}" / name


def write_fixture_source(
    root: Path,
    episodes: int = 3,
    frames: int = 45,
    corrupt: tuple[int, ...] = (),
    open_gripper: tuple[int, ...] = (),
) -> Path:
    """Write synthetic Episodes under `root`; those in `corrupt` get unreadable video, and in
    those in `open_gripper` the gripper never closes."""
    _write_parquet(root, episodes, frames, open_gripper)
    for index in range(episodes):
        # No two Episodes share a clip: recordings are replayed by clip path, and the Meta
        # client uploads and asks about identical clips only once.
        hue = f"=size=320x180:rate={FPS:g},hue=h={10 * index}"
        patterns = (f"testsrc{hue}", f"testsrc2{hue}", sliding_block(index))
        for camera, pattern in zip(CAMERAS, patterns, strict=True):
            path = clip_path(root, index, camera)
            if index in corrupt:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"not a video")
            else:
                write_clip(path, frames, pattern)
    return root
