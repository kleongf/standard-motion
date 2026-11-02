import hashlib
import sqlite3
from datetime import UTC, datetime

from standard_motion.baseline.models import (
    BaselineAnswer,
    EpisodeBaseline,
    FailBenchAnswer,
    FailBenchResult,
    SampleResult,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS baseline_answers (
    episode_id TEXT NOT NULL,
    description_sha TEXT NOT NULL,  -- '' for the FailBench check, which has no Description
    kind TEXT NOT NULL,  -- 'sample' | 'failbench'
    sample INTEGER NOT NULL,
    answer TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (episode_id, description_sha, kind, sample)
);
"""

SAMPLES = 3


def description_sha(description: str) -> str:
    return hashlib.sha256(description.encode()).hexdigest()


class BaselineStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        db.executescript(SCHEMA)

    def save_sample(
        self, episode_id: str, description: str, sample: int, answer: BaselineAnswer | None,
        error: str | None,
    ) -> None:  # fmt: skip
        self._save(episode_id, description_sha(description), "sample", sample, answer, error)

    def save_failbench(
        self, episode_id: str, answer: FailBenchAnswer | None, error: str | None
    ) -> None:
        self._save(episode_id, "", "failbench", 0, answer, error)

    def answers(self, episode_id: str, description: str) -> EpisodeBaseline:
        rows = self._db.execute(
            "SELECT * FROM baseline_answers WHERE episode_id = ? AND "
            "((kind = 'sample' AND description_sha = ?) OR kind = 'failbench') ORDER BY sample",
            (episode_id, description_sha(description)),
        ).fetchall()
        samples = [
            SampleResult(
                sample=r["sample"],
                answer=BaselineAnswer.model_validate_json(r["answer"]) if r["answer"] else None,
                error=r["error"],
            )
            for r in rows
            if r["kind"] == "sample"
        ]
        failbench = next(
            (
                FailBenchResult(
                    answer=FailBenchAnswer.model_validate_json(r["answer"])
                    if r["answer"]
                    else None,
                    error=r["error"],
                )
                for r in rows
                if r["kind"] == "failbench"
            ),
            None,
        )
        return EpisodeBaseline(samples=samples, failbench=failbench)

    def complete_count(self, description: str) -> int:
        """Episodes with every sample and the FailBench check answered."""
        row = self._db.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT episode_id FROM baseline_answers
                WHERE answer IS NOT NULL AND (
                    (kind = 'sample' AND description_sha = ?) OR kind = 'failbench')
                GROUP BY episode_id HAVING COUNT(*) = ?
            )
            """,
            (description_sha(description), SAMPLES + 1),
        ).fetchone()
        return int(row[0])

    def _save(
        self, episode_id: str, sha: str, kind: str, sample: int,
        answer: BaselineAnswer | FailBenchAnswer | None, error: str | None,
    ) -> None:  # fmt: skip
        self._db.execute(
            "INSERT OR REPLACE INTO baseline_answers VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                episode_id,
                sha,
                kind,
                sample,
                answer.model_dump_json() if answer else None,
                error,
                datetime.now(UTC).isoformat(),
            ),
        )
