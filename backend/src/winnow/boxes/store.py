import sqlite3
from datetime import UTC, datetime

from winnow.boxes.models import Box, BoxDraw

SCHEMA = """
CREATE TABLE IF NOT EXISTS boxes (
    episode_id TEXT PRIMARY KEY REFERENCES episodes(id),
    camera TEXT NOT NULL,
    x1 INTEGER NOT NULL,
    y1 INTEGER NOT NULL,
    x2 INTEGER NOT NULL,
    y2 INTEGER NOT NULL,
    frame_width INTEGER NOT NULL,
    frame_height INTEGER NOT NULL,
    drawn_at TEXT NOT NULL
);
"""


class BoxStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        db.executescript(SCHEMA)

    def save(self, episode_id: str, draw: BoxDraw, frame_size: tuple[int, int]) -> Box:
        """Replaces any earlier box for the Episode."""
        box = Box(
            episode_id=episode_id,
            frame_width=frame_size[0],
            frame_height=frame_size[1],
            drawn_at=datetime.now(UTC).isoformat(),
            **draw.model_dump(),
        )
        self._db.execute(
            "INSERT OR REPLACE INTO boxes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                box.episode_id,
                box.camera,
                box.x1,
                box.y1,
                box.x2,
                box.y2,
                box.frame_width,
                box.frame_height,
                box.drawn_at,
            ),
        )
        return box

    def get(self, episode_id: str) -> Box | None:
        row = self._db.execute("SELECT * FROM boxes WHERE episode_id = ?", (episode_id,)).fetchone()
        return None if row is None else Box.model_validate(dict(row))

    def list(self) -> list[Box]:
        rows = self._db.execute("SELECT * FROM boxes ORDER BY episode_id")
        return [Box.model_validate(dict(row)) for row in rows]

    def count(self) -> int:
        return int(self._db.execute("SELECT COUNT(*) FROM boxes").fetchone()[0])
