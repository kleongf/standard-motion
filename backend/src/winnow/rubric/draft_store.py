"""The Project's one Rubric draft: replaced by each compile, changed by edits, frozen by Run."""

import sqlite3

from winnow.rubric.models import RubricDraft

SCHEMA = """
CREATE TABLE IF NOT EXISTS rubric_draft (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- one draft per Project, one Project this week
    draft TEXT NOT NULL  -- JSON RubricDraft
);
"""


class DraftStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        db.executescript(SCHEMA)

    def get(self) -> RubricDraft | None:
        row = self._db.execute("SELECT draft FROM rubric_draft WHERE id = 1").fetchone()
        return None if row is None else RubricDraft.model_validate_json(row["draft"])

    def save(self, draft: RubricDraft) -> RubricDraft:
        self._db.execute(
            "INSERT INTO rubric_draft (id, draft) VALUES (1, ?) "
            "ON CONFLICT (id) DO UPDATE SET draft = excluded.draft",
            (draft.model_dump_json(exclude={"uncovered", "english"}),),
        )
        return draft
