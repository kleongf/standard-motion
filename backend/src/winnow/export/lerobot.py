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


def write_lerobot(source: ExportSource, indices: list[int], out: Path) -> None:
    info = source.info()
    chunks = int((info or {}).get("chunks_size") or CHUNKS_SIZE)
    table = source.rows(indices)
    keys = video_keys(table)
    rows: list[dict[str, Any]] = table.to_pylist()
    texts, task_numbers = _task_numbers(rows, source.task_texts())
    frames: list[pa.Table] = []
    exported: list[dict[str, Any]] = []
    first_clips: dict[str, Path] = {}
    start = 0
    for new, row in enumerate(rows):
        frames.append(renumbered(source.frames(row), new, start, task_numbers))
        clips = {key: _place(source, row, key, new, out, chunks) for key in keys}
        for key, (_, clip) in clips.items():
            first_clips.setdefault(key, clip)
        videos = {key: placed for key, (placed, _) in clips.items()}
        exported.append(_with_video_stats(rebased(row, new, start, videos, frames[-1]), clips))
        start += frames[-1].num_rows
    data = pa.concat_tables(frames)
    _write_parquet(data, out / DATA_PATH.format(chunk_index=0, file_index=0))
    _write_parquet(_episodes_table(exported, table.schema), out / EPISODES_PATH)
    _write_parquet(tasks_table(texts), out / "meta" / "tasks.parquet")
    stats = json.dumps(aggregate_stats(exported), indent=4)
    (out / "meta" / "stats.json").write_text(stats + "\n")
    features = {key: video_feature(clip, source.fps) for key, clip in first_clips.items()}
    meta = info_json(info, data, len(rows), len(texts), source.fps, features)
    (out / "meta" / "info.json").write_text(json.dumps(meta, indent=2) + "\n")
