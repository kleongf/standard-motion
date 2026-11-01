"""Synthetic droid_1.0.1-layout Episodes: meta/episodes and data parquet, and one shared mp4
per camera holding every Episode back to back, as the real dataset stores them: LeRobot encodes
each Episode on its own and joins them, so each starts on a keyframe, and droid_1.0.1's AV1 has
one every 2 frames and no B-frames."""

from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from winnow.episodes.droid101 import CAMERA_KEYS, FPS
from winnow.episodes.fixtures import state as droid100_state
from winnow.episodes.fixtures import write_clip

LENGTHS = (30, 45, 36, 42)
TASKS = ("Put the marker in the bowl", "", "Move the cup to the left", "Put the block in the box")
SUCCESS = (True, False, False, True)


def _meta(lengths: tuple[int, ...]) -> pa.Table:
    starts = np.concatenate([[0], np.cumsum(lengths)[:-1]])
    columns: dict[str, list[object]] = {
        "episode_index": list(range(len(lengths))),
        "tasks": [[TASKS[i % len(TASKS)]] for i in range(len(lengths))],
        "length": list(lengths),
        "data/chunk_index": [0] * len(lengths),
        "data/file_index": [0] * len(lengths),
        "stats/is_episode_successful/max": [[SUCCESS[i % 4]] for i in range(len(lengths))],
    }
    for key in CAMERA_KEYS.values():
        prefix = f"videos/observation.images.{key}"
        columns[f"{prefix}/chunk_index"] = [0] * len(lengths)
        columns[f"{prefix}/file_index"] = [0] * len(lengths)
        columns[f"{prefix}/from_timestamp"] = [float(s / FPS) for s in starts]
    return pa.table(columns)  # pyright: ignore[reportUnknownMemberType]


def _data(lengths: tuple[int, ...]) -> pa.Table:
    rows: dict[str, list[object]] = {name: [] for name in (
        "episode_index", "timestamp", "observation.state.cartesian_position",
        "observation.state.gripper_position", "observation.state.joint_position",
        "is_episode_successful", "language_instruction",
        *(f"camera_extrinsics.{key}" for key in CAMERA_KEYS.values()),
    )}  # fmt: skip
    for episode, length in enumerate(lengths):
        state = droid100_state(length)
        for frame in range(length):
            rows["episode_index"].append(episode)
            rows["timestamp"].append(frame / FPS)
            rows["observation.state.cartesian_position"].append([*map(float, state[frame, :6])])
            rows["observation.state.gripper_position"].append([float(state[frame, 6])])
            rows["observation.state.joint_position"].append([0.1 * j for j in range(7)])
            rows["is_episode_successful"].append(SUCCESS[episode % 4])
            rows["language_instruction"].append(TASKS[episode % len(TASKS)])
            for i, key in enumerate(CAMERA_KEYS.values()):
                rows[f"camera_extrinsics.{key}"].append([0.5, 0.1 * i, 0.4, 0.0, 0.5, 1.5])
    return pa.table(rows)  # pyright: ignore[reportUnknownMemberType]


def _keyframes(lengths: tuple[int, ...]) -> list[str]:
    """x264 options for a keyframe every 2 frames and on each Episode's first, no B-frames."""
    starts = np.concatenate([[0], np.cumsum(lengths)[:-1]])
    forced = "+".join(f"eq(n,{int(s)})" for s in starts)
    return ["-g", "2", "-bf", "0", "-force_key_frames", f"expr:{forced}"]


def write_droid101_fixture(
    root: Path, lengths: tuple[int, ...] = LENGTHS, episode_keyframes: bool = True
) -> Path:
    """Without `episode_keyframes`, the shared videos are encoded in one go with x264's defaults:
    their only keyframe is the first."""
    for folder, table in (
        ("meta/episodes/chunk-000", _meta(lengths)),
        ("data/chunk-000", _data(lengths)),
    ):
        (root / folder).mkdir(parents=True, exist_ok=True)
        pq.write_table(table, root / folder / "file-000.parquet")  # pyright: ignore[reportUnknownMemberType]
    for key, pattern in zip(
        CAMERA_KEYS.values(), ("testsrc", "testsrc2", "smptebars"), strict=True
    ):
        path = root / "videos" / f"observation.images.{key}" / "chunk-000" / "file-000.mp4"
        write_clip(path, sum(lengths), pattern, *(_keyframes(lengths) if episode_keyframes else []))
    return root
