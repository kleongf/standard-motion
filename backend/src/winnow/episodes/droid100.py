"""lerobot/droid_100: robot data from the v3.0 parquet, per-Episode clips from the v2.0 branch."""

from collections.abc import Callable
from functools import cached_property
from pathlib import Path
from typing import cast

import huggingface_hub
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from numpy.typing import NDArray

from winnow.episodes.clips import to_h264
from winnow.episodes.models import EpisodeSignals, SourceEpisode

REPO_ID = "lerobot/droid_100"
NAME = "droid_100"
FPS = 15.0
CAMERAS = ("exterior_image_1_left", "exterior_image_2_left", "wrist_image_left")

# (path in the repo, revision) -> local file
Fetch = Callable[[str, str], Path]

# huggingface_hub's overloads are partially untyped; pin the one signature we use.
_hf_download = cast(Callable[..., str], huggingface_hub.hf_hub_download)  # pyright: ignore[reportUnknownMemberType]


def hub_fetch(cache_dir: Path) -> Fetch:
    def fetch(path: str, revision: str) -> Path:
        local_dir = cache_dir / revision
        return Path(
            _hf_download(REPO_ID, path, repo_type="dataset", revision=revision, local_dir=local_dir)
        )

    return fetch


def local_fetch(root: Path) -> Fetch:
    """Read a copy laid out like the repo, one folder per revision (e.g. the test fixtures)."""

    def fetch(path: str, revision: str) -> Path:
        return root / revision / path

    return fetch


def _column(table: pa.Table, name: str, rows: NDArray[np.bool_]) -> NDArray[np.float64]:
    values = np.asarray(table.column(name).to_pylist(), dtype=np.float64)
    return values[rows]


class Droid100:
    name: str = NAME
    cameras: tuple[str, ...] = CAMERAS

    def __init__(self, fetch: Fetch) -> None:
        self.fetch = fetch  # the repo's files, which the exporter re-reads in full

    @cached_property
    def _table(self) -> pa.Table:
        path = self.fetch("data/chunk-000/file-000.parquet", "main")
        return pq.read_table(path)  # pyright: ignore[reportUnknownMemberType]

    @cached_property
    def _tasks(self) -> dict[int, str]:
        table = pq.read_table(self.fetch("meta/tasks.parquet", "main"))  # pyright: ignore[reportUnknownMemberType]
        indices = table.column("task_index").to_pylist()
        texts = table.column("__index_level_0__").to_pylist()
        return {int(str(i)): str(t) for i, t in zip(indices, texts, strict=True)}

    def load(self, index: int) -> SourceEpisode:
        table = self._table
        rows = np.asarray(table.column("episode_index").to_pylist()) == index
        if not rows.any():
            raise ValueError(f"droid_100 has no Episode {index}")
        state = _column(table, "observation.state", rows)
        signals = EpisodeSignals(
            episode_index=index,
            fps=FPS,
            timestamps=_column(table, "timestamp", rows),
            position=state[:, 0:3],
            gripper=state[:, 6],
            dataset_outcome=bool(_column(table, "next.reward", rows).sum() > 0),
        )
        task = int(_column(table, "task_index", rows)[0])
        instruction = self._tasks.get(task, "").strip() or None
        return SourceEpisode(signals, instruction)

    def write_clip(self, index: int, camera: str, out: Path) -> None:
        """Transcode the source's own (AV1) clip to H.264."""
        source = self.fetch(
            f"videos/chunk-000/observation.images.{camera}/episode_{index:06d}.mp4", "v2.0"
        )
        to_h264(source, out)
