import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from winnow.audit.models import AuditKind

# One row per sampled Episode. A sample is drawn once per Rubric version and margin multiplier s:
# written once, whole, and then only read, so drawing again at the same s returns it. Calibrating
# the version changes its s, and with it which Episodes it keeps, so the next draw is fresh.
SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_samples (
    rubric_version INTEGER NOT NULL,
    s REAL NOT NULL,  -- the version's margin multiplier when drawn
    seed INTEGER NOT NULL,
    episode_id TEXT NOT NULL REFERENCES episodes(id),
    kind TEXT NOT NULL,  -- 'keep' or 'reject': its Triage decision when drawn
    created_at TEXT NOT NULL,
    PRIMARY KEY (rubric_version, s, episode_id)
);
"""

# Samples drawn before s existed were all drawn at s = 1; the key changes, so the table is rebuilt.
MIGRATE_UNKEYED_BY_S = (
    """
ALTER TABLE audit_samples RENAME TO audit_samples_before_s;
"""
    + SCHEMA
    + """
INSERT INTO audit_samples (rubric_version, s, seed, episode_id, kind, created_at)
    SELECT rubric_version, 1.0, seed, episode_id, kind, created_at FROM audit_samples_before_s
    ORDER BY rowid;
DROP TABLE audit_samples_before_s;
"""
)


@dataclass(frozen=True)
class Pick:
    episode_id: str
    kind: AuditKind


@dataclass(frozen=True)
class StoredSample:
    rubric_version: int
    s: float
    seed: int
    created_at: str
    picks: list[Pick]  # in the order drawn


def _keyed_by_s(db: sqlite3.Connection) -> bool:
    columns = {row["name"] for row in db.execute("PRAGMA table_info(audit_samples)")}
    return not columns or "s" in columns


class AuditStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        if not _keyed_by_s(db):
            db.executescript(f"BEGIN; {MIGRATE_UNKEYED_BY_S} COMMIT;")
        db.executescript(SCHEMA)

    def get(self, rubric_version: int, s: float) -> StoredSample | None:
        rows = self._db.execute(
            "SELECT * FROM audit_samples WHERE rubric_version = ? AND s = ? ORDER BY rowid",
            (rubric_version, s),
        ).fetchall()
        if not rows:
            return None
        return StoredSample(
            rubric_version=rubric_version,
            s=s,
            seed=rows[0]["seed"],
            created_at=rows[0]["created_at"],
            picks=[Pick(row["episode_id"], row["kind"]) for row in rows],
        )

    def latest_s(self, rubric_version: int) -> float | None:
        """The s the version's most recent sample was drawn at; None when none was drawn."""
        row = self._db.execute(
            "SELECT s FROM audit_samples WHERE rubric_version = ? ORDER BY rowid DESC LIMIT 1",
            (rubric_version,),
        ).fetchone()
        return None if row is None else float(row["s"])

    def save(self, rubric_version: int, s: float, seed: int, picks: list[Pick]) -> StoredSample:
        """Writes the sample unless the version has one at `s`; returns whichever is stored."""
        with self._db:
            self._db.execute("BEGIN IMMEDIATE")
            if self.get(rubric_version, s) is None:
                at = datetime.now(UTC).isoformat()
                self._db.executemany(
                    "INSERT INTO audit_samples (rubric_version, s, seed, episode_id, kind, "
                    "created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    [(rubric_version, s, seed, p.episode_id, p.kind, at) for p in picks],
                )
        stored = self.get(rubric_version, s)
        assert stored is not None, "an empty sample isn't stored"
        return stored
