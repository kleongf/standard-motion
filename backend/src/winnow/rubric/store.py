"""Rubric versions: numbered, append-only and immutable once written."""

import sqlite3
from datetime import UTC, datetime

from winnow.core.db import ensure_column
from winnow.rubric.models import Rubric, RubricVersion

# The triggers keep a written version unchangeable even for a writer that skips this store.
SCHEMA = """
CREATE TABLE IF NOT EXISTS rubric_versions (
    version INTEGER PRIMARY KEY,
    rubric TEXT NOT NULL,  -- JSON Rubric
    created_at TEXT NOT NULL,
    origin TEXT NOT NULL DEFAULT 'seed'  -- 'seed' or 'run'
);
CREATE TRIGGER IF NOT EXISTS rubric_versions_no_update BEFORE UPDATE ON rubric_versions
BEGIN SELECT RAISE(ABORT, 'Rubric versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS rubric_versions_no_delete BEFORE DELETE ON rubric_versions
BEGIN SELECT RAISE(ABORT, 'Rubric versions are immutable'); END;
"""


class RubricStore:
    def __init__(self, db: sqlite3.Connection, seed: Rubric) -> None:
        """Writes `seed` as the next version when there is no version yet, or when the latest
        one is an older seed: until a Rubric is Run, the seed in the code is the Rubric."""
        self._db = db
        db.executescript(SCHEMA)
        ensure_column(db, "rubric_versions", "origin", "TEXT NOT NULL DEFAULT 'seed'")
        latest = db.execute(
            "SELECT rubric, origin FROM rubric_versions ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if latest is None or (
            latest["origin"] == "seed" and Rubric.model_validate_json(latest["rubric"]) != seed
        ):
            self._insert(seed, "seed")

    def add(self, rubric: Rubric) -> RubricVersion:
        """Freezes `rubric` as the next version."""
        return self._insert(rubric, "run")

    def _insert(self, rubric: Rubric, origin: str) -> RubricVersion:
        cursor = self._db.execute(
            "INSERT INTO rubric_versions (version, rubric, created_at, origin) "
            "SELECT COALESCE(MAX(version), 0) + 1, ?, ?, ? FROM rubric_versions",
            (rubric.model_dump_json(), datetime.now(UTC).isoformat(), origin),
        )
        version = self.get(int(cursor.lastrowid or 0))
        assert version is not None
        return version

    def get(self, version: int) -> RubricVersion | None:
        row = self._db.execute(
            "SELECT * FROM rubric_versions WHERE version = ?", (version,)
        ).fetchone()
        return None if row is None else self._version(row)

    def latest(self) -> RubricVersion:
        row = self._db.execute(
            "SELECT * FROM rubric_versions ORDER BY version DESC LIMIT 1"
        ).fetchone()
        return self._version(row)

    def list(self) -> list[RubricVersion]:
        """Every version, newest first."""
        rows = self._db.execute("SELECT * FROM rubric_versions ORDER BY version DESC")
        return [self._version(row) for row in rows]

    def _version(self, row: sqlite3.Row) -> RubricVersion:
        return RubricVersion(
            version=row["version"],
            created_at=row["created_at"],
            origin=row["origin"],
            rubric=Rubric.model_validate_json(row["rubric"]),
        )
