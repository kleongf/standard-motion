import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from standard_motion.selection.models import (
    Candidate,
    CandidateStatus,
    ExclusionReason,
    SelectionAnswer,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS selection_candidates (
    episode_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_index INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    task TEXT,
    answer TEXT,
    error TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    exclusion_reason TEXT,
    updated_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Sampled:
    """One Episode the selection pass drew."""

    episode_id: str
    source: str
    index: int
    seed: int
    task: str | None


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SelectionStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        db.executescript(SCHEMA)

    def has_answer(self, episode_id: str) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM selection_candidates WHERE episode_id = ? AND answer IS NOT NULL",
            (episode_id,),
        ).fetchone()
        return row is not None

    def save_answer(
        self, sampled: Sampled, answer: SelectionAnswer | None, error: str | None
    ) -> None:
        """Records Spark's reading; a decision already made is kept."""
        self._db.execute(
            """
            INSERT INTO selection_candidates
                (episode_id, source, source_index, seed, task, answer, error, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (episode_id) DO UPDATE SET
                answer = excluded.answer, error = excluded.error, updated_at = excluded.updated_at
            """,
            (
                sampled.episode_id,
                sampled.source,
                sampled.index,
                sampled.seed,
                sampled.task,
                answer.model_dump_json() if answer else None,
                error,
                _now(),
            ),
        )

    def decide(
        self, episode_id: str, status: CandidateStatus, reason: ExclusionReason | None
    ) -> Candidate | None:
        self._db.execute(
            "UPDATE selection_candidates SET status = ?, exclusion_reason = ?, updated_at = ? "
            "WHERE episode_id = ?",
            (status, reason, _now(), episode_id),
        )
        return self.get(episode_id)

    def _rows(self, where: str, params: tuple[object, ...]) -> list[Candidate]:
        rows = self._db.execute(
            "SELECT c.*, e.id IS NOT NULL AS ingested FROM selection_candidates c "
            f"LEFT JOIN episodes e ON e.id = c.episode_id {where} ORDER BY c.source_index",
            params,
        )
        return [_candidate(row) for row in rows]

    def get(self, episode_id: str) -> Candidate | None:
        rows = self._rows("WHERE c.episode_id = ?", (episode_id,))
        return rows[0] if rows else None

    def list(self) -> list[Candidate]:
        return self._rows("", ())


def _candidate(row: sqlite3.Row) -> Candidate:
    answer = SelectionAnswer.model_validate_json(row["answer"]) if row["answer"] else None
    return Candidate(
        episode_id=row["episode_id"],
        source=row["source"],
        index=row["source_index"],
        seed=row["seed"],
        task=row["task"],
        pick_and_place=answer.pick_and_place if answer else None,
        object=answer.object if answer else None,
        target=answer.target if answer else None,
        error=row["error"],
        status=row["status"],
        exclusion_reason=row["exclusion_reason"],
        ingested=bool(row["ingested"]),
    )
