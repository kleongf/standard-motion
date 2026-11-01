"""The Test run log: every Test set run, dated, with its Rubric version and report. Append-only,
so the reported numbers are provably the last run before the freeze."""

import sqlite3
from datetime import UTC, datetime

from winnow.evaluation.models import EvaluationReport, TestRun

SCHEMA = """
CREATE TABLE IF NOT EXISTS test_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    rubric_version INTEGER NOT NULL,
    report TEXT NOT NULL  -- JSON EvaluationReport
);
CREATE TRIGGER IF NOT EXISTS test_runs_no_update BEFORE UPDATE ON test_runs
BEGIN SELECT RAISE(ABORT, 'The Test run log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS test_runs_no_delete BEFORE DELETE ON test_runs
BEGIN SELECT RAISE(ABORT, 'The Test run log is append-only'); END;
"""


class TestRunLog:
    __test__ = False  # not a pytest class

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        db.executescript(SCHEMA)

    def append(self, report: EvaluationReport) -> TestRun:
        run_at = datetime.now(UTC).isoformat()
        cursor = self._db.execute(
            "INSERT INTO test_runs (run_at, rubric_version, report) VALUES (?, ?, ?)",
            (run_at, report.rubric_version, report.model_dump_json()),
        )
        return TestRun(
            id=int(cursor.lastrowid or 0),
            run_at=run_at,
            rubric_version=report.rubric_version,
            report=report,
        )

    def list(self) -> list[TestRun]:
        """Newest first."""
        rows = self._db.execute("SELECT * FROM test_runs ORDER BY id DESC")
        return [
            TestRun(
                id=row["id"],
                run_at=row["run_at"],
                rubric_version=row["rubric_version"],
                report=EvaluationReport.model_validate_json(row["report"]),
            )
            for row in rows
        ]
