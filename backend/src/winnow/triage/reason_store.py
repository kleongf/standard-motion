"""Spark's Reasons, each under the `triage.spark_reason.reason_key` it was written for; Triage
swaps one in over the template Reason only while the Episode's key still matches."""

import sqlite3
from datetime import UTC, datetime

from pydantic import TypeAdapter

from winnow.criteria.models import TextSpan

SCHEMA = """
CREATE TABLE IF NOT EXISTS spark_reasons (
    episode_id TEXT NOT NULL REFERENCES episodes(id),
    key TEXT NOT NULL,
    spans TEXT NOT NULL,  -- JSON list of TextSpan
    written_at TEXT NOT NULL,
    PRIMARY KEY (episode_id, key)
);
"""

_SPANS = TypeAdapter(list[TextSpan])


class SparkReasonStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        db.executescript(SCHEMA)

    def get(self, episode_id: str, key: str) -> list[TextSpan] | None:
        row = self._db.execute(
            "SELECT spans FROM spark_reasons WHERE episode_id = ? AND key = ?", (episode_id, key)
        ).fetchone()
        return None if row is None else _SPANS.validate_json(row["spans"])

    def put(self, episode_id: str, key: str, spans: list[TextSpan]) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO spark_reasons VALUES (?, ?, ?, ?)",
            (episode_id, key, _SPANS.dump_json(spans).decode(), datetime.now(UTC).isoformat()),
        )

    def keys(self) -> set[tuple[str, str]]:
        """Every (Episode id, key) a Reason is stored under."""
        rows = self._db.execute("SELECT episode_id, key FROM spark_reasons")
        return {(r["episode_id"], r["key"]) for r in rows}
