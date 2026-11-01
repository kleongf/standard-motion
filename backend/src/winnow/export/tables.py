"""Renumbering an Episode's rows: its frames in the data parquet and its meta/episodes row, moved
to a new Episode index, a new place in the dataset's frames and new video files."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
import pyarrow as pa

from winnow.export.stats import QUANTILES, episode_stats

TASK_TEXT = "__index_level_0__"  # LeRobot writes tasks with pandas, the text as the index
# What pandas needs to read the text back as the index, as LeRobot does.
_PANDAS = {
    "index_columns": [TASK_TEXT],
    "column_indexes": [],
    "columns": [
        {"name": "task_index", "field_name": "task_index", "pandas_type": "int64",
         "numpy_type": "int64", "metadata": None},
        {"name": None, "field_name": TASK_TEXT, "pandas_type": "unicode",
         "numpy_type": "object", "metadata": None},
    ],
}  # fmt: skip


@dataclass(frozen=True)
class Placed:
    """Where an exported Episode's video for one camera went."""

    chunk: int
    file: int
    from_timestamp: float  # the Episode's start within that file


def task_texts(tasks: pa.Table) -> dict[int, str]:
    """task_index -> task text, from a LeRobot meta/tasks.parquet."""
    text = TASK_TEXT if TASK_TEXT in tasks.column_names else "task"
    indices = tasks.column("task_index").to_pylist()
    return {
        int(str(i)): str(t) for i, t in zip(indices, tasks.column(text).to_pylist(), strict=True)
    }


def tasks_table(texts: list[str]) -> pa.Table:
    table = pa.table(  # pyright: ignore[reportUnknownMemberType]
        {
            "task_index": pa.array(range(len(texts)), type=pa.int64()),
            TASK_TEXT: pa.array(texts, type=pa.string()),
        }
    )
    return table.replace_schema_metadata({"pandas": json.dumps(_PANDAS)})


def _replaced(table: pa.Table, name: str, values: list[Any]) -> pa.Table:
    position = table.schema.get_field_index(name)
    if position < 0:
        return table
    field = cast("pa.Field[pa.DataType]", table.schema.field(name))  # pyright: ignore[reportUnknownMemberType]
    return table.set_column(position, field, pa.array(values, type=field.type))


def renumbered(frames: pa.Table, new: int, start: int, tasks: Mapping[int, int]) -> pa.Table:
    """One Episode's frames as Episode `new`, its first frame the dataset's `start`th, with task
    indices mapped to the exported tasks'."""
    count = frames.num_rows
    table = _replaced(frames, "episode_index", [new] * count)
    table = _replaced(table, "index", list(range(start, start + count)))
    if "task_index" in table.column_names:
        old = [int(str(t)) for t in table.column("task_index").to_pylist()]
        unknown = sorted(set(old) - set(tasks))
        if unknown:
            raise ValueError(f"task_index {unknown[0]} has no task among the exported Episodes'")
        table = _replaced(table, "task_index", [tasks[t] for t in old])
    return table


def _shifted(row: dict[str, Any], column: str, delta: int) -> None:
    """Add `delta` to a stats column's min, max, mean and quantiles (one-item lists); its std
    doesn't change."""
    for stat in ("min", "max", "mean", *QUANTILES):
        name = f"stats/{column}/{stat}"
        if name in row and row[name] is not None:
            row[name] = (np.asarray(row[name]) + delta).tolist()


def _set(row: dict[str, Any], values: Mapping[str, object]) -> None:
    """Set the columns the source has."""
    for name, value in values.items():
        if name in row:
            row[name] = value


def rebased(
    source_row: Mapping[str, Any],
    new: int,
    start: int,
    videos: Mapping[str, Placed],
    frames: pa.Table,
) -> dict[str, Any]:
    """An Episode's meta/episodes row, every column kept, moved to Episode `new`, the frames from
    `start` in the one data file, and its videos where they were placed. `frames` are its
    exported frames: task indices are mapped onto the exported tasks in no particular order, so
    their stats are taken from these again rather than shifted."""
    row = dict(source_row)
    old_start = int(row.get("dataset_from_index") or 0)
    _shifted(row, "episode_index", new - int(row["episode_index"]))
    _shifted(row, "index", start - old_start)
    if "task_index" in frames.column_names:
        _set(row, episode_stats(frames.select(["task_index"])))
    row["episode_index"] = new
    _set(row, {
        "data/chunk_index": 0, "data/file_index": 0,
        "dataset_from_index": start, "dataset_to_index": start + int(row["length"]),
        "meta/episodes/chunk_index": 0, "meta/episodes/file_index": 0,
    })  # fmt: skip
    for key, placed in videos.items():
        prefix = f"videos/{key}"
        span = None
        if row.get(f"{prefix}/to_timestamp") is not None:
            span = float(row[f"{prefix}/to_timestamp"]) - float(row[f"{prefix}/from_timestamp"])
        row[f"{prefix}/chunk_index"] = placed.chunk
        row[f"{prefix}/file_index"] = placed.file
        row[f"{prefix}/from_timestamp"] = placed.from_timestamp
        if span is not None:
            row[f"{prefix}/to_timestamp"] = placed.from_timestamp + span
    return row


def video_keys(rows: pa.Table) -> list[str]:
    """The cameras with video, from meta/episodes' `videos/<key>/from_timestamp` columns."""
    suffix = "/from_timestamp"
    return [
        name.removeprefix("videos/").removesuffix(suffix)
        for name in rows.column_names
        if name.startswith("videos/") and name.endswith(suffix)
    ]
