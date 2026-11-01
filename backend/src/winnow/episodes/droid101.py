"""lerobot/droid_1.0.1 (LeRobot v3.0): robot data, joints and camera extrinsics in shared
parquet files, and each camera's video as stretches of shared mp4s, located per Episode by
meta/episodes. Its cameras map onto droid_100's names, which the rest of the app uses."""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from winnow.episodes import droid100
from winnow.episodes.clips import cut_h264, tile_frames
from winnow.episodes.droid101_files import Files
from winnow.episodes.models import EpisodeSignals, FloatArray, SourceEpisode

NAME = "droid_1.0.1"
FPS = 15.0
CAMERAS = droid100.CAMERAS
# droid_100's camera name -> droid_1.0.1's
CAMERA_KEYS = {
    "exterior_image_1_left": "exterior_1_left",
    "exterior_image_2_left": "exterior_2_left",
    "wrist_image_left": "wrist_left",
}
META_FOLDER = "meta/episodes/chunk-000"
VIDEO = "videos/{key}/chunk-{chunk:03d}/file-{file:03d}.mp4"
DATA = "data/chunk-{chunk:03d}/file-{file:03d}.parquet"
SUCCESS = "stats/is_episode_successful/max"
DATA_COLUMNS = [
    "episode_index",
    "timestamp",
    "observation.state.cartesian_position",
    "observation.state.gripper_position",
    "observation.state.joint_position",
    "is_episode_successful",
    "language_instruction",
    *(f"camera_extrinsics.{key}" for key in CAMERA_KEYS.values()),
]


def _video_columns() -> list[str]:
    fields = ("chunk_index", "file_index", "from_timestamp")
    return [f"videos/observation.images.{k}/{f}" for k in CAMERA_KEYS.values() for f in fields]


META_COLUMNS = [
    "episode_index",
    "tasks",
    "length",
    "data/chunk_index",
    "data/file_index",
    SUCCESS,
    *_video_columns(),
]


@dataclass(frozen=True)
class EpisodeMeta:
    index: int
    length: int  # frames
    flagged_success: bool  # the Dataset outcome
    task: str | None
    row: Mapping[str, Any]  # the meta/episodes row, for locating data and video


def _first(value: Any) -> Any:  # noqa: ANN401 (stats columns come back as one-item lists)
    return value[0] if isinstance(value, list) else value  # pyright: ignore[reportUnknownVariableType]


def _array(table: pa.Table, column: str) -> FloatArray:
    return np.asarray(table.column(column).to_pylist(), dtype=np.float64)


class Droid101:
    name: str = NAME
    cameras: tuple[str, ...] = CAMERAS

    def __init__(self, files: Files) -> None:
        self.files = files  # the repo's files, which the exporter re-reads in full
        self._data: tuple[str, pa.Table] | None = None  # the last data file read

    @cached_property
    def index(self) -> dict[int, EpisodeMeta]:
        """Every Episode's meta row (read by column, a few seconds per file from the Hub)."""
        found: dict[int, EpisodeMeta] = {}
        for path in self.files.list(META_FOLDER):
            with self.files.open(path) as f:
                table = pq.read_table(f, columns=META_COLUMNS)  # pyright: ignore[reportUnknownMemberType]
            for row in table.to_pylist():
                tasks: list[str] = row["tasks"] or []
                episode = EpisodeMeta(
                    index=int(row["episode_index"]),
                    length=int(row["length"]),
                    flagged_success=bool(_first(row[SUCCESS])),
                    task=(tasks[0].strip() or None) if tasks else None,
                    row=row,
                )
                found[episode.index] = episode
        return found

    def meta(self, index: int) -> EpisodeMeta:
        if index not in self.index:
            raise ValueError(f"droid_1.0.1 has no Episode {index}")
        return self.index[index]

    def load(self, index: int) -> SourceEpisode:
        row = self.meta(index).row
        table = self._data_table(
            DATA.format(chunk=row["data/chunk_index"], file=row["data/file_index"])
        )
        rows = np.asarray(table.column("episode_index").to_pylist()) == index
        episode = table.filter(pa.array(rows.tolist(), type=pa.bool_()))
        cartesian = _array(episode, "observation.state.cartesian_position")
        signals = EpisodeSignals(
            episode_index=index,
            fps=FPS,
            timestamps=_array(episode, "timestamp"),
            position=cartesian[:, 0:3],
            gripper=_array(episode, "observation.state.gripper_position").reshape(-1),
            dataset_outcome=bool(episode.column("is_episode_successful")[0].as_py()),
            joint_positions=_array(episode, "observation.state.joint_position"),
            camera_extrinsics={
                camera: _array(episode, f"camera_extrinsics.{key}")
                for camera, key in CAMERA_KEYS.items()
            },
        )
        instruction = str(episode.column("language_instruction")[0].as_py() or "").strip()
        return SourceEpisode(signals, instruction or None)

    def write_clip(self, index: int, camera: str, out: Path) -> None:
        """Cut this Episode's stretch of the camera's shared video, as H.264."""
        source, start = self._video(index, camera)
        cut_h264(source, start, self.meta(index).length, out)

    def write_tiles(self, index: int, camera: str, count: int, out: Path) -> None:
        """`count` frames evenly through the Episode, side by side, for a contact sheet."""
        source, start = self._video(index, camera)
        tile_frames(source, start, self.meta(index).length / FPS, count, out)

    def _video(self, index: int, camera: str) -> tuple[str, float]:
        row = self.meta(index).row
        prefix = f"videos/observation.images.{CAMERA_KEYS[camera]}"
        path = VIDEO.format(
            key=f"observation.images.{CAMERA_KEYS[camera]}",
            chunk=row[f"{prefix}/chunk_index"],
            file=row[f"{prefix}/file_index"],
        )
        return self.files.video_input(path), float(row[f"{prefix}/from_timestamp"])

    def _data_table(self, path: str) -> pa.Table:
        if self._data is None or self._data[0] != path:
            with self.files.open(path) as f:
                table = pq.read_table(f, columns=DATA_COLUMNS)  # pyright: ignore[reportUnknownMemberType]
            self._data = (path, table)
        return self._data[1]
