import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime

from winnow.labels.models import StoredLabel
from winnow.triage.models import LabelSource

# The sources scoring applies. Audit labels feed only Keep precision, so they never override a
# Phrase's result, nor supersede an interview or review label on it.
SCORED: tuple[LabelSource, ...] = ("interview", "review")

# Append-only: a new answer for a Phrase supersedes the last one but never erases it, and undoing
# an interview answer withdraws its label rather than deleting it, so every label stays in
# history. The newest label per Phrase that isn't withdrawn is in force.
SCHEMA = """
CREATE TABLE IF NOT EXISTS labels (
    id INTEGER PRIMARY KEY,
    episode_id TEXT NOT NULL REFERENCES episodes(id),
    phrase TEXT NOT NULL,
    source TEXT NOT NULL,
    value TEXT NOT NULL,
    rubric_version INTEGER,  -- NULL: given against the Rubric draft (the interview)
    labelled_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS labels_by_episode ON labels (episode_id, phrase);
CREATE TRIGGER IF NOT EXISTS labels_no_update BEFORE UPDATE ON labels
BEGIN SELECT RAISE(ABORT, 'Labels are kept as history'); END;
CREATE TRIGGER IF NOT EXISTS labels_no_delete BEFORE DELETE ON labels
BEGIN SELECT RAISE(ABORT, 'Labels are kept as history'); END;
CREATE TABLE IF NOT EXISTS label_withdrawals (
    label_id INTEGER PRIMARY KEY REFERENCES labels(id),
    withdrawn_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS label_withdrawals_no_update BEFORE UPDATE ON label_withdrawals
BEGIN SELECT RAISE(ABORT, 'Labels are kept as history'); END;
CREATE TRIGGER IF NOT EXISTS label_withdrawals_no_delete BEFORE DELETE ON label_withdrawals
BEGIN SELECT RAISE(ABORT, 'Labels are kept as history'); END;
"""

SELECT = (
    "SELECT labels.*, label_withdrawals.withdrawn_at FROM labels "
    "LEFT JOIN label_withdrawals ON label_withdrawals.label_id = labels.id "
)


class LabelStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        db.executescript(SCHEMA)

    def add(self, label: StoredLabel) -> StoredLabel:
        """The label as stored, with its id."""
        cursor = self._db.execute(
            "INSERT INTO labels (episode_id, phrase, source, value, rubric_version, labelled_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                label.episode_id,
                label.phrase,
                label.source,
                label.value,
                label.rubric_version,
                label.labelled_at,
            ),
        )
        return label.model_copy(update={"id": cursor.lastrowid})

    def withdraw(self, label_id: int) -> None:
        """Stops a label applying; the Phrase's previous label, if any, is in force again."""
        self._db.execute(
            "INSERT OR IGNORE INTO label_withdrawals (label_id, withdrawn_at) VALUES (?, ?)",
            (label_id, datetime.now(UTC).isoformat()),
        )

    def history(self, episode_id: str) -> list[StoredLabel]:
        """Every label the Episode was ever given, withdrawn or not, oldest first."""
        rows = self._db.execute(SELECT + "WHERE episode_id = ? ORDER BY labels.id", (episode_id,))
        return [self._label(row) for row in rows]

    def in_force(
        self, episode_id: str, sources: Sequence[LabelSource] = SCORED
    ) -> list[StoredLabel]:
        """The newest label for each Phrase that isn't withdrawn, among those from `sources`: by
        default the ones scoring applies."""
        marks = ",".join("?" * len(sources))
        rows = self._db.execute(
            SELECT + "WHERE labels.id IN (SELECT MAX(id) FROM labels WHERE episode_id = ? "
            f"AND source IN ({marks}) "
            "AND id NOT IN (SELECT label_id FROM label_withdrawals) GROUP BY phrase) "
            "ORDER BY labels.id",
            (episode_id, *sources),
        )
        return [self._label(row) for row in rows]

    def _label(self, row: sqlite3.Row) -> StoredLabel:
        return StoredLabel(
            id=row["id"],
            episode_id=row["episode_id"],
            phrase=row["phrase"],
            source=row["source"],
            value=row["value"],
            rubric_version=row["rubric_version"],
            labelled_at=row["labelled_at"],
            withdrawn_at=row["withdrawn_at"],
        )
