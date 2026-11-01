"""Ingested Episodes: a row each in SQLite, and their robot data and clips under the data dir."""

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import numpy as np

from winnow.core.db import ensure_column
from winnow.episodes.models import Episode, EpisodeSignals, SourceEpisode

SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_index INTEGER NOT NULL,
    instruction TEXT,
    dataset_outcome INTEGER,
    frames INTEGER NOT NULL,
    fps REAL NOT NULL,
    duration_s REAL NOT NULL,
    ingested_at TEXT NOT NULL
);
"""


def episode_id(source: str, index: int) -> str:
    return f"{source}:{index}"


def clip_path(folder: Path, camera: str) -> Path:
    return folder / f"{camera}.mp4"


def sam_clip_path(folder: Path, camera: str) -> Path:
    return folder / f"{camera}.5fps.mp4"


def frame0_path(folder: Path, camera: str) -> Path:
    return folder / f"{camera}.frame0.jpg"


def cameras_with_clips(folder: Path) -> list[str]:
    return sorted(p.stem for p in folder.glob("*.mp4") if "." not in p.stem)


# numpy's stubs read **arrays as its own keyword arguments; pin the call we make.
_savez = cast(Callable[..., None], np.savez)


def save_signals(folder: Path, signals: EpisodeSignals) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    optional = (
        {"joint_positions": signals.joint_positions} if signals.joint_positions is not None else {}
    )
    for camera, extrinsics in (signals.camera_extrinsics or {}).items():
        optional[f"extrinsics.{camera}"] = extrinsics
    _savez(
        folder / "signals.npz",
        timestamps=signals.timestamps,
        position=signals.position,
        gripper=signals.gripper,
        **optional,
    )


class EpisodeStore:
    def __init__(self, db: sqlite3.Connection, data_dir: Path) -> None:
        self._db = db
        self._root = data_dir / "episodes"
        db.executescript(SCHEMA)
        ensure_column(db, "episodes", "task_object", "TEXT")
        ensure_column(db, "episodes", "task_target", "TEXT")
        # Where the source dropped the instruction, the Reference labeller writes one.
        ensure_column(db, "episodes", "written_instruction", "TEXT")

    def folder(self, source: str, index: int) -> Path:
        return self._root / source / f"{index:06d}"

    def is_ingested(self, source: str, index: int, cameras: tuple[str, ...]) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM episodes WHERE id = ?", (episode_id(source, index),)
        ).fetchone()
        folder = self.folder(source, index)
        files = [folder / "signals.npz"]
        files += [clip_path(folder, c) for c in cameras] + [
            sam_clip_path(folder, c) for c in cameras
        ]
        return row is not None and all(f.exists() for f in files)

    def save(self, source: str, index: int, episode: SourceEpisode) -> None:
        s = episode.signals
        duration = float(s.timestamps[-1] - s.timestamps[0]) + 1 / s.fps if len(s.timestamps) else 0
        self._db.execute(
            "INSERT OR REPLACE INTO episodes (id, source, source_index, instruction, "
            "dataset_outcome, frames, fps, duration_s, ingested_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                episode_id(source, index),
                source,
                index,
                episode.instruction,
                s.dataset_outcome,
                len(s.timestamps),
                s.fps,
                round(duration, 3),
                datetime.now(UTC).isoformat(),
            ),
        )

    def set_task(self, id: str, task_object: str | None, task_target: str | None) -> None:
        self._db.execute(
            "UPDATE episodes SET task_object = ?, task_target = ? WHERE id = ?",
            (task_object, task_target, id),
        )

    def write_instruction(self, id: str, instruction: str) -> None:
        self._db.execute(
            "UPDATE episodes SET written_instruction = ? WHERE id = ?", (instruction, id)
        )

    def list(self) -> list[Episode]:
        rows = self._db.execute("SELECT * FROM episodes ORDER BY source, source_index")
        return [self._episode(row) for row in rows]

    def get(self, id: str) -> Episode | None:
        row = self._db.execute("SELECT * FROM episodes WHERE id = ?", (id,)).fetchone()
        return None if row is None else self._episode(row)

    def episode_folder(self, episode: Episode) -> Path:
        return self.folder(episode.source, episode.index)

    def load_signals(self, episode: Episode) -> EpisodeSignals:
        with np.load(self.episode_folder(episode) / "signals.npz") as saved:
            return EpisodeSignals(
                episode_index=episode.index,
                fps=episode.fps,
                timestamps=saved["timestamps"],
                position=saved["position"],
                gripper=saved["gripper"],
                dataset_outcome=episode.dataset_outcome,
                joint_positions=saved.get("joint_positions"),
                camera_extrinsics={
                    name.removeprefix("extrinsics."): saved[name]
                    for name in saved.files
                    if name.startswith("extrinsics.")
                }
                or None,
            )

    def count_by_source(self) -> dict[str, int]:
        rows = self._db.execute("SELECT source, COUNT(*) AS n FROM episodes GROUP BY source")
        return {str(r["source"]): int(r["n"]) for r in rows}

    def _episode(self, row: sqlite3.Row) -> Episode:
        outcome = row["dataset_outcome"]
        return Episode(
            id=row["id"],
            source=row["source"],
            index=row["source_index"],
            instruction=row["instruction"] or row["written_instruction"],
            dataset_outcome=None if outcome is None else bool(outcome),
            frames=row["frames"],
            fps=row["fps"],
            duration_s=row["duration_s"],
            cameras=cameras_with_clips(self.folder(row["source"], row["source_index"])),
            task_object=row["task_object"],
            task_target=row["task_target"],
        )
