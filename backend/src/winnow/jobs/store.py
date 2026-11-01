import json
import os
import sqlite3
from collections import Counter
from datetime import UTC, datetime

from winnow.core.db import ensure_column
from winnow.jobs.models import Job, JobItem, Status, WorkItem

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL,
    owner_pid INTEGER
);
CREATE TABLE IF NOT EXISTS job_items (
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    position INTEGER NOT NULL,
    step TEXT NOT NULL,
    args TEXT NOT NULL,
    label TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT,
    updated_at TEXT NOT NULL,
    after_position INTEGER,
    PRIMARY KEY (job_id, position)
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _alive(pid: int | None) -> bool:
    """Whether the process that owns a job still runs; a job from before owners were recorded
    has none, and counts as dead."""
    if pid is None:
        return False
    try:
        os.kill(pid, 0)  # signal 0 only checks the process exists
    except ProcessLookupError:
        return False
    except PermissionError:  # it exists, under another user
        pass
    return True


class JobStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        db.executescript(SCHEMA)
        ensure_column(db, "job_items", "after_position", "INTEGER")
        ensure_column(db, "jobs", "owner_pid", "INTEGER")

    def create(self, kind: str, items: list[WorkItem]) -> int:
        """Record a job owned by this process, which runs it."""
        with self._db:
            self._db.execute("BEGIN")
            cursor = self._db.execute(
                "INSERT INTO jobs (kind, created_at, owner_pid) VALUES (?, ?, ?)",
                (kind, _now(), os.getpid()),
            )
            job_id = int(cursor.lastrowid or 0)
            self._db.executemany(
                "INSERT INTO job_items (job_id, position, step, args, label, status, "
                "updated_at, after_position) VALUES (?, ?, ?, ?, ?, 'queued', ?, ?)",
                [
                    (
                        job_id,
                        i,
                        item.step,
                        json.dumps(dict(item.args)),
                        item.label,
                        _now(),
                        item.after,
                    )
                    for i, item in enumerate(items)
                ],
            )
        return job_id

    def queued(self, job_id: int) -> list[tuple[int, WorkItem]]:
        rows = self._db.execute(
            "SELECT * FROM job_items WHERE job_id = ? AND status = 'queued' ORDER BY position",
            (job_id,),
        )
        return [
            (
                int(r["position"]),
                WorkItem(r["step"], json.loads(r["args"]), r["label"], r["after_position"]),
            )
            for r in rows
        ]

    def in_flight(self, kind: str) -> list[dict[str, object]]:
        """The args of every item still queued or running in a job of `kind`."""
        rows = self._db.execute(
            "SELECT job_items.args FROM job_items JOIN jobs ON jobs.id = job_items.job_id "
            "WHERE jobs.kind = ? AND job_items.status IN ('queued', 'running')",
            (kind,),
        )
        return [json.loads(r["args"]) for r in rows]

    def set_status(self, job_id: int, position: int, status: Status, detail: str | None) -> None:
        self._db.execute(
            "UPDATE job_items SET status = ?, detail = ?, updated_at = ? "
            "WHERE job_id = ? AND position = ?",
            (status, detail, _now(), job_id, position),
        )

    def fail_interrupted(self) -> None:
        """Items left queued or running by a process that is gone will never finish: say so.
        Another live process's items (the CLI's, or another server's on the same data dir) are
        still running, so they are left alone."""
        unfinished = self._db.execute(
            "SELECT DISTINCT jobs.id, jobs.owner_pid FROM jobs "
            "JOIN job_items ON job_items.job_id = jobs.id "
            "WHERE job_items.status IN ('queued', 'running')"
        )
        dead = [(row["id"],) for row in unfinished if not _alive(row["owner_pid"])]
        with self._db:
            self._db.execute("BEGIN")
            self._db.executemany(
                "UPDATE job_items SET status = 'failed', detail = 'interrupted; run it again' "
                "WHERE job_id = ? AND status IN ('queued', 'running')",
                dead,
            )

    def get(self, job_id: int) -> Job | None:
        row = self._db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return None if row is None else self._job(row)

    def latest(self, kind: str) -> Job | None:
        row = self._db.execute(
            "SELECT * FROM jobs WHERE kind = ? ORDER BY id DESC LIMIT 1", (kind,)
        ).fetchone()
        return None if row is None else self._job(row)

    def _job(self, row: sqlite3.Row) -> Job:
        items = [
            JobItem(
                position=r["position"],
                step=r["step"],
                label=r["label"],
                status=r["status"],
                detail=r["detail"],
            )
            for r in self._db.execute(
                "SELECT * FROM job_items WHERE job_id = ? ORDER BY position", (row["id"],)
            )
        ]
        counts = Counter(item.status for item in items)
        return Job(
            id=row["id"],
            kind=row["kind"],
            created_at=row["created_at"],
            total=len(items),
            queued=counts["queued"],
            running=counts["running"],
            done=counts["done"],
            failed=counts["failed"],
            finished=counts["queued"] + counts["running"] == 0,
            items=items,
        )
