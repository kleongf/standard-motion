import sqlite3

from pydantic import TypeAdapter

from winnow.reference_labels.models import PhraseLabel, ReferenceLabel

# One first pass and at most one relabel per Episode. A saved label never changes: labelling
# reveals the Dataset outcome, so a later edit would no longer be blind.
SCHEMA = """
CREATE TABLE IF NOT EXISTS reference_labels (
    episode_id TEXT NOT NULL REFERENCES episodes(id),
    relabel INTEGER NOT NULL,
    description TEXT NOT NULL,
    phrases TEXT NOT NULL,
    instruction TEXT,
    elapsed_s REAL NOT NULL,
    labelled_at TEXT NOT NULL,
    PRIMARY KEY (episode_id, relabel)
);
CREATE TRIGGER IF NOT EXISTS reference_labels_stay BEFORE UPDATE ON reference_labels
BEGIN SELECT RAISE(ABORT, 'Reference labels never change'); END;
CREATE TRIGGER IF NOT EXISTS reference_labels_stay_put BEFORE DELETE ON reference_labels
BEGIN SELECT RAISE(ABORT, 'Reference labels never change'); END;
"""

_phrases = TypeAdapter(list[PhraseLabel])


class ReferenceLabelStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        db.executescript(SCHEMA)

    def add(self, label: ReferenceLabel) -> None:
        """Raises sqlite3.IntegrityError if the Episode already has a label for this pass."""
        self._db.execute(
            "INSERT INTO reference_labels VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                label.episode_id,
                label.relabel,
                label.description,
                _phrases.dump_json(label.phrases).decode(),
                label.instruction,
                label.elapsed_s,
                label.labelled_at,
            ),
        )

    def list(self) -> list[ReferenceLabel]:
        rows = self._db.execute(
            "SELECT reference_labels.* FROM reference_labels "
            "JOIN episodes ON episodes.id = episode_id ORDER BY relabel, source, source_index"
        )
        return [self._label(row) for row in rows]

    def has(self, episode_id: str, *, relabel: bool) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM reference_labels WHERE episode_id = ? AND relabel = ?",
            (episode_id, relabel),
        ).fetchone()
        return row is not None

    def labelled_ids(self) -> set[str]:
        """Episodes with a first-pass label; a relabel alone doesn't count."""
        rows = self._db.execute("SELECT episode_id FROM reference_labels WHERE relabel = 0")
        return {str(r["episode_id"]) for r in rows}

    def _label(self, row: sqlite3.Row) -> ReferenceLabel:
        return ReferenceLabel(
            episode_id=row["episode_id"],
            relabel=bool(row["relabel"]),
            description=row["description"],
            phrases=_phrases.validate_json(row["phrases"]),
            instruction=row["instruction"],
            elapsed_s=row["elapsed_s"],
            labelled_at=row["labelled_at"],
        )
