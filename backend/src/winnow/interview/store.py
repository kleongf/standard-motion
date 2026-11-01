"""Interview answers, kept per Rubric draft (by its `compiled_at`). A compile afresh starts a new
interview; a recompile of an edit carries the answers that still hold over to the recompiled
draft (`interview.carry`), leaving the old draft's answers as they were. Undo removes an answer
here (its label stays in the label store's history, withdrawn)."""

import sqlite3

from winnow.interview.models import StoredAnswer

SCHEMA = """
CREATE TABLE IF NOT EXISTS interview_answers (
    id INTEGER PRIMARY KEY,
    compiled_at TEXT NOT NULL,  -- the draft it answers
    answer TEXT NOT NULL  -- JSON StoredAnswer
);
"""


class InterviewStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        db.executescript(SCHEMA)

    def add(self, compiled_at: str, answer: StoredAnswer) -> StoredAnswer:
        cursor = self._db.execute(
            "INSERT INTO interview_answers (compiled_at, answer) VALUES (?, '')", (compiled_at,)
        )
        assert cursor.lastrowid is not None
        stored = answer.model_copy(update={"id": cursor.lastrowid})
        self._db.execute(
            "UPDATE interview_answers SET answer = ? WHERE id = ?",
            (stored.model_dump_json(), stored.id),
        )
        return stored

    def answers(self, compiled_at: str) -> list[StoredAnswer]:
        """The draft's answers, oldest first."""
        rows = self._db.execute(
            "SELECT answer FROM interview_answers WHERE compiled_at = ? ORDER BY id",
            (compiled_at,),
        )
        return [StoredAnswer.model_validate_json(row["answer"]) for row in rows]

    def remove(self, ids: list[int]) -> None:
        self._db.executemany("DELETE FROM interview_answers WHERE id = ?", [(i,) for i in ids])
