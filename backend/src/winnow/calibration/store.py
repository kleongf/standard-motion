import sqlite3
from datetime import UTC, datetime

from winnow.calibration.models import CalibrationRecord
from winnow.triage.confidence import UNCALIBRATED

# Append-only: calibrating a version again adds a row, and the newest row is its s. A version
# with no row, such as a new one, is scored at s = 1.
SCHEMA = """
CREATE TABLE IF NOT EXISTS calibrations (
    id INTEGER PRIMARY KEY,
    rubric_version INTEGER NOT NULL,
    s REAL NOT NULL,
    n_labels INTEGER NOT NULL,
    errors INTEGER NOT NULL,
    bound_met INTEGER NOT NULL,  -- 0: no s met the bound, so s is the widest
    unstable INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS calibrations_by_version ON calibrations (rubric_version);
"""


class CalibrationStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        db.executescript(SCHEMA)

    def add(
        self,
        rubric_version: int,
        s: float,
        n_labels: int,
        errors: int,
        bound_met: bool,
        unstable: bool,
    ) -> CalibrationRecord:
        at = datetime.now(UTC).isoformat()
        self._db.execute(
            "INSERT INTO calibrations (rubric_version, s, n_labels, errors, bound_met, unstable, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (rubric_version, s, n_labels, errors, int(bound_met), int(unstable), at),
        )
        latest = self.latest(rubric_version)
        assert latest is not None
        return latest

    def latest(self, rubric_version: int) -> CalibrationRecord | None:
        row = self._db.execute(
            "SELECT * FROM calibrations WHERE rubric_version = ? ORDER BY id DESC LIMIT 1",
            (rubric_version,),
        ).fetchone()
        if row is None:
            return None
        return CalibrationRecord(
            rubric_version=row["rubric_version"],
            s=row["s"],
            n_labels=row["n_labels"],
            errors=row["errors"],
            bound_met=bool(row["bound_met"]),
            unstable=bool(row["unstable"]),
            created_at=row["created_at"],
        )

    def s_for(self, rubric_version: int) -> float:
        """The margin multiplier the version is scored with: its latest calibration's, else 1."""
        latest = self.latest(rubric_version)
        return UNCALIBRATED if latest is None else latest.s
