"""The Audit store keys a sample by Rubric version and margin multiplier s; samples stored
before s existed were drawn at s = 1."""

import sqlite3
from pathlib import Path

from winnow.audit.store import AuditStore, Pick
from winnow.core.db import open_db

BEFORE_S = """
CREATE TABLE audit_samples (
    rubric_version INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    episode_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (rubric_version, episode_id)
);
INSERT INTO audit_samples VALUES (1, 7, 'droid_100:0', 'keep', '2026-10-29T00:00:00+00:00');
INSERT INTO audit_samples VALUES (1, 7, 'droid_100:2', 'reject', '2026-10-29T00:00:00+00:00');
"""


def db_at(path: Path) -> sqlite3.Connection:
    """No Episodes are stored here, so their foreign keys aren't checked."""
    db = open_db(path / "winnow.db")
    db.execute("PRAGMA foreign_keys=OFF")
    return db


def test_a_sample_stored_before_s_existed_is_kept_as_drawn_at_s_1(tmp_path: Path):
    db = db_at(tmp_path)
    db.executescript(BEFORE_S)

    store = AuditStore(db)

    old = store.get(1, 1.0)
    assert old is not None and (old.seed, old.s) == (7, 1.0)
    assert old.picks == [Pick("droid_100:0", "keep"), Pick("droid_100:2", "reject")]
    assert store.get(1, 2.0) is None


def test_the_same_episode_can_be_drawn_again_at_another_s(tmp_path: Path):
    store = AuditStore(db_at(tmp_path))
    store.save(1, 1.0, 7, [Pick("droid_100:0", "keep")])

    again = store.save(1, 0.5, 8, [Pick("droid_100:0", "keep"), Pick("droid_100:1", "keep")])

    assert (again.s, again.seed, len(again.picks)) == (0.5, 8, 2)
    assert store.latest_s(1) == 0.5
    assert store.latest_s(2) is None
    assert store.save(1, 1.0, 9, []).seed == 7  # drawn once at each s
