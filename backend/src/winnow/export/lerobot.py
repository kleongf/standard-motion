"""Writes chosen Episodes of a source as one LeRobot v3.0 dataset, renumbered from 0 in the
order given: every column of the source's data, one data file, and one video file per Episode
and camera, located by meta/episodes, with meta/stats.json combining their stats (a camera's
computed from its clip where the source has none)."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol, cast

import pyarrow as pa
import pyarrow.parquet as pq

from winnow.export.info import CHUNKS_SIZE, DATA_PATH, VIDEO_PATH, info_json, video_feature
from winnow.export.stats import aggregate_stats
from winnow.export.tables import Placed, rebased, renumbered, tasks_table, video_keys
from winnow.export.video_stats import video_stats

EPISODES_PATH = "meta/episodes/chunk-000/file-000.parquet"


class ExportSource(Protocol):
    """A source's files as LeRobot rows: what the exporter re-reads, every column of it."""

    fps: float

    def info(self) -> dict[str, Any] | None:
        """The source's meta/info.json, if it has one."""
        ...

    def task_texts(self) -> dict[int, str]:
        """The source's task_index -> task text, if it numbers tasks."""
        ...

    def rows(self, indices: list[int]) -> pa.Table:
        """These Episodes' meta/episodes rows, in this order."""
        ...

    def frames(self, row: Mapping[str, Any]) -> pa.Table:
        """The Episode's rows of the data parquet."""
        ...

    def write_video(self, row: Mapping[str, Any], key: str, out: Path) -> float:
        """Write the Episode's video for camera `key`; returns where it starts in `out`."""
        ...


def _task_numbers(
    rows: list[dict[str, Any]], source: Mapping[int, str]
) -> tuple[list[str], dict[int, int]]:
    """The exported tasks, in order of first use, and the source's task_index -> exported."""
    used: list[str] = [str(t) for row in rows for t in cast(list[object], row.get("tasks") or [])]
    texts = list(dict.fromkeys(used))
    numbers = {text: i for i, text in enumerate(texts)}
    return texts, {old: numbers[text] for old, text in source.items() if text in numbers}


def _write_parquet(table: pa.Table, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)  # pyright: ignore[reportUnknownMemberType]


def _place(
    source: ExportSource, row: Mapping[str, Any], key: str, new: int, out: Path, chunks: int
) -> tuple[Placed, Path]:
    chunk, file = divmod(new, chunks)
    path = out / VIDEO_PATH.format(video_key=key, chunk_index=chunk, file_index=file)
    return Placed(chunk, file, source.write_video(row, key, path)), path


def _with_video_stats(
    row: dict[str, Any], clips: Mapping[str, tuple[Placed, Path]]
) -> dict[str, Any]:
    """The row with each camera's stats, computed from its exported clip where the source has
    none: LeRobot's training reads them for every camera."""
    for key, (placed, clip) in clips.items():
        if row.get(f"stats/{key}/mean") is None:
            row |= video_stats(clip, placed.from_timestamp, int(row["length"]), key)
    return row


def _episodes_table(rows: list[dict[str, Any]], source: pa.Schema) -> pa.Table:
    """The exported meta/episodes, in the source's schema plus any stats columns added."""
    added = [name for name in rows[0] if source.get_field_index(name) < 0] if rows else []
    if not added:
        return pa.Table.from_pylist(rows, schema=source)
    extra = pa.Table.from_pylist([{name: row[name] for name in added} for row in rows]).schema
    return pa.Table.from_pylist(rows, schema=pa.unify_schemas([source, extra]))


class LerobotWriter:
    """Writes the dataset an Episode at a time, so an export can report each one: `write` takes
    the chosen Episodes in order, then `finish` writes the tables that need them all."""

    def __init__(self, source: ExportSource, indices: list[int], out: Path) -> None:
        self._source, self._out = source, out
        self._info = source.info()
        self._chunks = int((self._info or {}).get("chunks_size") or CHUNKS_SIZE)
        self._table = source.rows(indices)
        self._keys = video_keys(self._table)
        self._rows: list[dict[str, Any]] = self._table.to_pylist()
        self._texts, self._task_numbers = _task_numbers(self._rows, source.task_texts())
        self._frames: list[pa.Table] = []
        self._exported: list[dict[str, Any]] = []
        self._first_clips: dict[str, Path] = {}
        self._start = 0

    @property
    def written(self) -> int:
        return len(self._exported)

    def write(self) -> None:
        """The next Episode's frames and clips."""
        new = self.written
        row = self._rows[new]
        frames = renumbered(self._source.frames(row), new, self._start, self._task_numbers)
        clips = {
            key: _place(self._source, row, key, new, self._out, self._chunks) for key in self._keys
        }
        for key, (_, clip) in clips.items():
            self._first_clips.setdefault(key, clip)
        videos = {key: placed for key, (placed, _) in clips.items()}
        self._frames.append(frames)
        self._exported.append(
            _with_video_stats(rebased(row, new, self._start, videos, frames), clips)
        )
        self._start += frames.num_rows

    def finish(self) -> None:
        """The data, meta/episodes, tasks, stats and info, once every Episode is written."""
        out, rows = self._out, self._exported
        if len(rows) != len(self._rows):
            raise ValueError(f"{len(rows)} of {len(self._rows)} Episodes written to {out}")
        data = pa.concat_tables(self._frames)
        _write_parquet(data, out / DATA_PATH.format(chunk_index=0, file_index=0))
        _write_parquet(_episodes_table(rows, self._table.schema), out / EPISODES_PATH)
        _write_parquet(tasks_table(self._texts), out / "meta" / "tasks.parquet")
        stats = json.dumps(aggregate_stats(rows), indent=4)
        (out / "meta" / "stats.json").write_text(stats + "\n")
        fps = self._source.fps
        features = {key: video_feature(clip, fps) for key, clip in self._first_clips.items()}
        meta = info_json(self._info, data, len(rows), len(self._texts), fps, features)
        (out / "meta" / "info.json").write_text(json.dumps(meta, indent=2) + "\n")


def write_lerobot(source: ExportSource, indices: list[int], out: Path) -> None:
    writer = LerobotWriter(source, indices, out)
    for _ in indices:
        writer.write()
    writer.finish()
