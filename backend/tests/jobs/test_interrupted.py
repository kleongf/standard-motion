"""Starting the app fails a job's unfinished items only when the process that owns it is gone."""

import sqlite3
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from winnow.app import create_app
from winnow.core.db import open_db
from winnow.core.settings import Settings
from winnow.jobs.models import WorkItem
from winnow.jobs.store import JobStore

INTERRUPTED = "interrupted; run it again"
ITEMS = [WorkItem("ingest", {"index": i}, f"droid_100:{i}") for i in range(3)]

# A process that records a job, starts one of its items, and exits without finishing them.
CREATE_AND_EXIT = """
import sys
from pathlib import Path
from winnow.core.db import open_db
from winnow.jobs.models import WorkItem
from winnow.jobs.store import JobStore

store = JobStore(open_db(Path(sys.argv[1])))
job_id = store.create("ingest", [WorkItem("ingest", {"index": i}, str(i)) for i in range(3)])
store.set_status(job_id, 0, "running", None)
print(job_id)
"""


def _statuses(api: TestClient, job_id: int) -> list[tuple[str, str | None]]:
    job = api.get(f"/api/jobs/{job_id}").json()
    return [(item["status"], item["detail"]) for item in job["items"]]


def test_a_live_processs_job_survives_another_app_starting(settings: Settings) -> None:
    # This test process owns the job, as the CLI owned its `winnow select` job.
    db = open_db(settings.db_path)
    store = JobStore(db)
    job_id = store.create("ingest", ITEMS)
    store.set_status(job_id, 0, "running", None)

    with TestClient(create_app(settings)) as api:
        statuses = _statuses(api, job_id)
    db.close()

    assert statuses == [("running", None), ("queued", None), ("queued", None)]


def test_a_dead_processs_job_is_failed_as_interrupted(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True)
    created = subprocess.run(
        [sys.executable, "-c", CREATE_AND_EXIT, str(settings.db_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    job_id = int(created.stdout)

    with TestClient(create_app(settings)) as api:
        statuses = _statuses(api, job_id)

    assert statuses == [("failed", INTERRUPTED)] * 3


def test_a_job_from_before_owners_were_recorded_is_failed_as_interrupted(
    settings: Settings,
) -> None:
    _write_ownerless_job(settings.db_path)

    with TestClient(create_app(settings)) as api:
        statuses = _statuses(api, 1)

    assert statuses == [("done", None), ("failed", INTERRUPTED), ("failed", INTERRUPTED)]


def _write_ownerless_job(db_path: Path) -> None:
    """A job as the schema before owners stored it: no owner column at all."""
    db_path.parent.mkdir(parents=True)
    db = sqlite3.connect(db_path)
    with db:
        db.executescript(
            """
            CREATE TABLE jobs (id INTEGER PRIMARY KEY, kind TEXT NOT NULL,
                created_at TEXT NOT NULL);
            CREATE TABLE job_items (job_id INTEGER NOT NULL REFERENCES jobs(id),
                position INTEGER NOT NULL, step TEXT NOT NULL, args TEXT NOT NULL,
                label TEXT NOT NULL, status TEXT NOT NULL, detail TEXT,
                updated_at TEXT NOT NULL, after_position INTEGER,
                PRIMARY KEY (job_id, position));
            INSERT INTO jobs VALUES (1, 'ingest', '2026-10-28T00:00:00+00:00');
            INSERT INTO job_items VALUES
                (1, 0, 'ingest', '{}', '0', 'done', NULL, '2026-10-28T00:00:00+00:00', NULL),
                (1, 1, 'ingest', '{}', '1', 'running', NULL, '2026-10-28T00:00:00+00:00', NULL),
                (1, 2, 'ingest', '{}', '2', 'queued', NULL, '2026-10-28T00:00:00+00:00', NULL);
            """
        )
    db.close()
