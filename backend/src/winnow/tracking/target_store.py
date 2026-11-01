"""Target boxes, at the Dataset level: per Episode, SAM's and the curator's, kept side by side so
redrawing one never loses the other."""

import sqlite3

from winnow.tracking.models import FrameBox, TargetBox

SCHEMA = """
CREATE TABLE IF NOT EXISTS target_boxes (
    episode_id TEXT NOT NULL REFERENCES episodes(id),
    origin TEXT NOT NULL,  -- 'sam' | 'hand'
    camera TEXT NOT NULL,
    status TEXT NOT NULL,  -- 'found' | 'not_found' | 'no_instruction' | 'no_target'
    target TEXT,
    box TEXT,  -- JSON FrameBox, or NULL unless found
    frame_width INTEGER NOT NULL,
    frame_height INTEGER NOT NULL,
    made_at TEXT NOT NULL,
    PRIMARY KEY (episode_id, origin)
);
"""


class TargetBoxStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        db.executescript(SCHEMA)

    def save(self, target: TargetBox) -> TargetBox:
        """Replaces the Episode's earlier target box of the same origin."""
        self._db.execute(
            "INSERT OR REPLACE INTO target_boxes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                target.episode_id,
                target.origin,
                target.camera,
                target.status,
                target.target,
                target.box.model_dump_json() if target.box else None,
                target.frame_width,
                target.frame_height,
                target.made_at,
            ),
        )
        return target

    def for_episode(self, episode_id: str) -> list[TargetBox]:
        rows = self._db.execute(
            "SELECT * FROM target_boxes WHERE episode_id = ? ORDER BY origin", (episode_id,)
        )
        return [self._target(row) for row in rows]

    def _target(self, row: sqlite3.Row) -> TargetBox:
        fields = dict(row)
        box = fields.pop("box")
        return TargetBox(box=FrameBox.model_validate_json(box) if box else None, **fields)
