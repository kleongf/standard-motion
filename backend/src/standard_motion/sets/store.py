import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime

from standard_motion.sets.models import SET_NAMES, EpisodeSet, SetName

# An Episode is in at most one set (the members' primary key), and the triggers keep a frozen
# set's membership and timestamp unchangeable even for a writer that skips the service's checks.
SCHEMA = """
CREATE TABLE IF NOT EXISTS episode_sets (
    name TEXT PRIMARY KEY,
    frozen_at TEXT
);
CREATE TABLE IF NOT EXISTS set_members (
    episode_id TEXT PRIMARY KEY REFERENCES episodes(id),
    set_name TEXT NOT NULL REFERENCES episode_sets(name),
    added_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS set_members_frozen_insert BEFORE INSERT ON set_members
WHEN (SELECT frozen_at FROM episode_sets WHERE name = NEW.set_name) IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'set is frozen'); END;
CREATE TRIGGER IF NOT EXISTS set_members_frozen_delete BEFORE DELETE ON set_members
WHEN (SELECT frozen_at FROM episode_sets WHERE name = OLD.set_name) IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'set is frozen'); END;
CREATE TRIGGER IF NOT EXISTS set_members_frozen_update BEFORE UPDATE ON set_members
WHEN (SELECT frozen_at FROM episode_sets WHERE name IN (OLD.set_name, NEW.set_name)
      AND frozen_at IS NOT NULL) IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'set is frozen'); END;
CREATE TRIGGER IF NOT EXISTS episode_sets_stay_frozen BEFORE UPDATE ON episode_sets
WHEN OLD.frozen_at IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'set is frozen'); END;
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SetStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        db.executescript(SCHEMA)
        db.executemany(
            "INSERT OR IGNORE INTO episode_sets (name) VALUES (?)", [(n,) for n in SET_NAMES]
        )

    def list(self) -> list[EpisodeSet]:
        return [self.get(name) for name in SET_NAMES]

    def get(self, name: SetName) -> EpisodeSet:
        row = self._db.execute("SELECT * FROM episode_sets WHERE name = ?", (name,)).fetchone()
        ids = [
            str(r["episode_id"])
            for r in self._db.execute(
                "SELECT episode_id FROM set_members JOIN episodes ON episodes.id = episode_id "
                "WHERE set_name = ? ORDER BY source, source_index",
                (name,),
            )
        ]
        return EpisodeSet(name=name, size=len(ids), frozen_at=row["frozen_at"], episode_ids=ids)

    def sets_of(self, episode_ids: Sequence[str]) -> dict[str, SetName]:
        """The set each of these Episodes is in, for those in one."""
        marks = ",".join("?" * len(episode_ids))
        rows = self._db.execute(
            f"SELECT episode_id, set_name FROM set_members WHERE episode_id IN ({marks})",
            episode_ids,
        )
        return {str(r["episode_id"]): r["set_name"] for r in rows}

    def add(self, name: SetName, episode_ids: Sequence[str]) -> None:
        """All or nothing. Raises sqlite3.IntegrityError if any is already in a set."""
        with self._db:
            self._db.execute("BEGIN")
            self._db.executemany(
                "INSERT INTO set_members (episode_id, set_name, added_at) VALUES (?, ?, ?)",
                [(episode_id, name, _now()) for episode_id in episode_ids],
            )

    def remove(self, name: SetName, episode_id: str) -> bool:
        cursor = self._db.execute(
            "DELETE FROM set_members WHERE set_name = ? AND episode_id = ?", (name, episode_id)
        )
        return cursor.rowcount > 0

    def freeze(self, name: SetName) -> None:
        self._db.execute("UPDATE episode_sets SET frozen_at = ? WHERE name = ?", (_now(), name))
