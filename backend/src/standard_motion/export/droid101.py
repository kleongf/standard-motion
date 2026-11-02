"""droid_1.0.1's files as the exporter reads them: meta/episodes and data parquet with every
column, and each Episode's stretch of a camera's shared video, copied without re-encoding."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from standard_motion.episodes.clips import copy_cut, cut_h264, frame_checksum, probe
from standard_motion.episodes.droid101 import DATA, FPS, META_FOLDER, VIDEO, Droid101
from standard_motion.export.tables import task_texts


def _only(table: pa.Table, indices: list[int]) -> pa.Table:
    """The rows of these Episodes, in this order."""
    episodes = np.asarray(table.column("episode_index").to_pylist())
    order = [int(i) for index in indices for i in np.flatnonzero(episodes == index)]
    return table.take(pa.array(order, type=pa.int64()))


def _same(clip: Path, source: str, start: float, length: int) -> bool:
    """Whether `clip` holds `length` frames, its first and last the source's from `start`."""
    if probe(clip)[0] != length:
        return False
    last = (length - 1) / FPS
    return all(
        frame_checksum(str(clip), t) == frame_checksum(source, start + t) for t in (0.0, last)
    )


class Droid101Export:
    fps: float = FPS

    def __init__(self, source: Droid101) -> None:
        self._files = source.files
        self._data: tuple[str, pa.Table] | None = None  # the last data file read

    def _read(self, path: str, columns: list[str] | None = None) -> pa.Table:
        with self._files.open(path) as f:
            return pq.read_table(f, columns=columns)  # pyright: ignore[reportUnknownMemberType]

    def info(self) -> dict[str, Any] | None:
        if "meta/info.json" not in self._files.list("meta"):
            return None
        with self._files.open("meta/info.json") as f:
            return json.load(f)

    def task_texts(self) -> dict[int, str]:
        if "meta/tasks.parquet" not in self._files.list("meta"):
            return {}
        return task_texts(self._read("meta/tasks.parquet"))

    def rows(self, indices: list[int]) -> pa.Table:
        wanted = set(indices)
        found: list[pa.Table] = []
        for path in self._files.list(META_FOLDER):
            listed = self._read(path, ["episode_index"]).column("episode_index").to_pylist()
            if wanted.intersection(int(str(i)) for i in listed):
                found.append(self._read(path))
        if not found:
            raise ValueError(f"droid_1.0.1 has none of Episodes {indices}")
        return _only(pa.concat_tables(found), indices)

    def frames(self, row: Mapping[str, Any]) -> pa.Table:
        path = DATA.format(chunk=row["data/chunk_index"], file=row["data/file_index"])
        if self._data is None or self._data[0] != path:
            self._data = (path, self._read(path))
        return _only(self._data[1], [int(row["episode_index"])])

    def write_video(self, row: Mapping[str, Any], key: str, out: Path) -> float:
        """A stream copy of exactly the Episode's frames; re-encoded instead (as lossless H.264,
        so every frame decodes the same) if it doesn't start on a keyframe, or the copy came out
        with another number of frames or another first or last frame than the source's."""
        prefix = f"videos/{key}"
        path = VIDEO.format(
            key=key, chunk=row[f"{prefix}/chunk_index"], file=row[f"{prefix}/file_index"]
        )
        source, start = self._files.video_input(path), float(row[f"{prefix}/from_timestamp"])
        length = int(row["length"])
        if not (copy_cut(source, start, length, out) and _same(out, source, start, length)):
            cut_h264(source, start, length, out, lossless=True)
        return 0.0
