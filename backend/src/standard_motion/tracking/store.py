"""SAM tracks, one per Episode and kind, at the Dataset level. Health is computed on read."""

import json
import sqlite3
from datetime import UTC, datetime

from standard_motion.tracking.health import track_health
from standard_motion.tracking.models import Track, TrackBox, TrackKind

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    episode_id TEXT NOT NULL REFERENCES episodes(id),
    kind TEXT NOT NULL,
    camera TEXT NOT NULL,
    status TEXT NOT NULL,  -- 'tracked' | 'no_closure'
    fps REAL NOT NULL,
    frames INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    seed_frame INTEGER,
    boxes TEXT NOT NULL,  -- JSON list of TrackBox
    created_at TEXT NOT NULL,
    PRIMARY KEY (episode_id, kind)
);
"""


class TrackStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        db.executescript(SCHEMA)

    def save(self, track: Track) -> None:
        """Replaces any earlier track of the same kind for the Episode."""
        self._db.execute(
            "INSERT OR REPLACE INTO tracks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                track.episode_id,
                track.kind,
                track.camera,
                track.status,
                track.fps,
                track.frames,
                track.width,
                track.height,
                track.seed_frame,
                json.dumps([b.model_dump() for b in track.boxes]),
                datetime.now(UTC).isoformat(),
            ),
        )

    def for_episode(self, episode_id: str) -> list[Track]:
        rows = self._db.execute(
            "SELECT * FROM tracks WHERE episode_id = ? ORDER BY kind", (episode_id,)
        )
        return [self._track(row) for row in rows]

    def count(self, kind: TrackKind, status: str) -> int:
        row = self._db.execute(
            "SELECT COUNT(*) FROM tracks WHERE kind = ? AND status = ?", (kind, status)
        ).fetchone()
        return int(row[0])

    def _track(self, row: sqlite3.Row) -> Track:
        boxes = [TrackBox.model_validate(b) for b in json.loads(row["boxes"])]
        tracked = row["status"] == "tracked"
        return Track(
            episode_id=row["episode_id"],
            kind=row["kind"],
            camera=row["camera"],
            status=row["status"],
            fps=row["fps"],
            frames=row["frames"],
            width=row["width"],
            height=row["height"],
            seed_frame=row["seed_frame"],
            boxes=boxes,
            health=track_health(boxes, row["frames"]) if tracked else None,
        )
