"""The app's one SQLite file (WAL, stdlib sqlite3, no ORM). Each feature creates its own tables."""

import sqlite3
from pathlib import Path


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Autocommit (wrap multi-row writes yourself). One connection may be used from several
    # threads, e.g. a test reading what the app's loop wrote; SQLite serializes access.
    db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")  # the CLI and the app may write at once
    db.execute("PRAGMA foreign_keys=ON")
    return db


def ensure_column(db: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
    """Add a column to a table an older version created without it."""
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
