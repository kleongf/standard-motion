"""droid_100's files as the exporter reads them: the data parquet with every column, and each
Episode's own mp4 per camera, copied as it is. Its meta/episodes rows are made from the data,
since the per-Episode clips come from another revision than the shared videos they'd locate."""

import json
import shutil
from collections.abc import Mapping
from functools import cached_property
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from huggingface_hub.errors import EntryNotFoundError

from winnow.episodes.droid100 import CAMERAS, FPS, Droid100
from winnow.export.stats import episode_stats
from winnow.export.tables import task_texts

KEY = "observation.images."


class Droid100Export:
    fps: float = FPS

    def __init__(self, source: Droid100) -> None:
        self._fetch = source.fetch

    @cached_property
    def _data(self) -> pa.Table:
        return pq.read_table(self._fetch("data/chunk-000/file-000.parquet", "main"))  # pyright: ignore[reportUnknownMemberType]

    def info(self) -> dict[str, Any] | None:
        try:
            path = self._fetch("meta/info.json", "main")
        except EntryNotFoundError:
            return None
        return json.loads(path.read_text()) if path.exists() else None

    def task_texts(self) -> dict[int, str]:
        return task_texts(pq.read_table(self._fetch("meta/tasks.parquet", "main")))  # pyright: ignore[reportUnknownMemberType]

    def _rows_of(self, index: int) -> np.ndarray:
        return np.flatnonzero(np.asarray(self._data.column("episode_index").to_pylist()) == index)

    def _episode(self, index: int) -> pa.Table:
        return self._data.take(pa.array(self._rows_of(index), type=pa.int64()))

    def rows(self, indices: list[int]) -> pa.Table:
        """Each Episode's row as LeRobot writes it, its stats computed from its frames: video
        stats aren't, since the clips aren't read."""
        tasks = self.task_texts()
        rows: list[dict[str, Any]] = []
        for index in indices:
            frames = self._episode(index)
            task = int(str(frames.column("task_index")[0].as_py()))
            start, length = int(self._rows_of(index)[0]), frames.num_rows
            row: dict[str, Any] = {
                "episode_index": index,
                "tasks": [tasks.get(task, "")],
                "length": length,
                "data/chunk_index": 0,
                "data/file_index": 0,
                "dataset_from_index": start,
                "dataset_to_index": start + length,
            }
            for camera in CAMERAS:
                prefix = f"videos/{KEY}{camera}"
                row |= {f"{prefix}/chunk_index": 0, f"{prefix}/file_index": 0}
                row |= {f"{prefix}/from_timestamp": 0.0, f"{prefix}/to_timestamp": length / FPS}
            rows.append(row | episode_stats(frames))
        return pa.Table.from_pylist(rows)

    def frames(self, row: Mapping[str, Any]) -> pa.Table:
        return self._episode(int(row["episode_index"]))

    def write_video(self, row: Mapping[str, Any], key: str, out: Path) -> float:
        camera = key.removeprefix(KEY)
        name = f"episode_{int(row['episode_index']):06d}.mp4"
        clip = self._fetch(f"videos/chunk-000/{KEY}{camera}/{name}", "v2.0")
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(clip, out)
        return 0.0
