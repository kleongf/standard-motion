"""Spark's answers to each visual Criterion asked of an Episode, with the clip they're about.

Keyed by `visual.keys.ask_key`, so an edit that leaves the prompts, views, window and crop alone
still finds them. The Meta cache stays the source of truth: running the steps again rebuilds
every row from cache hits.
"""

import sqlite3
from datetime import UTC, datetime

from winnow.visual.models import VisualAnswers, VisualClip, VisualSample

SCHEMA = """
CREATE TABLE IF NOT EXISTS visual_answers (
    episode_id TEXT NOT NULL REFERENCES episodes(id),
    ask_key TEXT NOT NULL,
    answers TEXT NOT NULL,  -- JSON VisualAnswers
    updated_at TEXT NOT NULL,
    PRIMARY KEY (episode_id, ask_key)
);
"""


class VisualStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        db.executescript(SCHEMA)

    def get(self, episode_id: str, ask_key: str) -> VisualAnswers | None:
        row = self._db.execute(
            "SELECT answers FROM visual_answers WHERE episode_id = ? AND ask_key = ?",
            (episode_id, ask_key),
        ).fetchone()
        return None if row is None else VisualAnswers.model_validate_json(row["answers"])

    def for_episode(self, episode_id: str) -> dict[str, VisualAnswers]:
        rows = self._db.execute(
            "SELECT ask_key, answers FROM visual_answers WHERE episode_id = ?", (episode_id,)
        )
        return {r["ask_key"]: VisualAnswers.model_validate_json(r["answers"]) for r in rows}

    def save_clip(self, episode_id: str, ask_key: str, clip: VisualClip) -> None:
        """A new clip clears the answers about the old one; the same clip keeps them."""
        found = self.get(episode_id, ask_key)
        samples = found.samples if found and found.clip == clip else []
        self._save(episode_id, ask_key, VisualAnswers(clip=clip, samples=samples, error=None))

    def save_samples(self, episode_id: str, ask_key: str, samples: list[VisualSample]) -> None:
        found = self.get(episode_id, ask_key)
        clip = found.clip if found else None
        self._save(episode_id, ask_key, VisualAnswers(clip=clip, samples=samples, error=None))

    def save_error(self, episode_id: str, ask_key: str, error: str) -> None:
        self._save(episode_id, ask_key, VisualAnswers(clip=None, samples=[], error=error))

    def _save(self, episode_id: str, ask_key: str, answers: VisualAnswers) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO visual_answers VALUES (?, ?, ?, ?)",
            (episode_id, ask_key, answers.model_dump_json(), datetime.now(UTC).isoformat()),
        )
