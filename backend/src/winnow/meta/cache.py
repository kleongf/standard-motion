"""Every Meta response, memoized by a hash of the full request, in the app's SQLite file."""

import hashlib
import json
import sqlite3
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from winnow.meta.models import Audio, Image, Part, Text, Video
from winnow.meta.transport import Reply

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta_cache (
    key TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    text TEXT NOT NULL,
    usage TEXT NOT NULL,
    usd REAL NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta_uploads (
    sha256 TEXT PRIMARY KEY,
    file_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class CachedReply:
    key: str
    model: str
    reply: Reply
    usd: float  # what the call cost when it was made, so evaluation can still price a cached run


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _part_key(part: Part) -> dict[str, str]:
    match part:
        case Text(text):
            return {"text": text}
        case Video(path):
            return {"video": file_sha256(path)}
        case Image(path):
            return {"image": file_sha256(path)}
        case Audio(path):
            return {"audio": file_sha256(path)}


def request_key(
    model: str, parts: tuple[Part, ...], options: Mapping[str, object], sample: int = 0
) -> str:
    """Files are keyed by content, so a re-encoded clip at the same path is a new request."""
    request = {
        "model": model,
        "parts": [_part_key(p) for p in parts],
        "options": options,
        "sample": sample,
    }
    canonical = json.dumps(request, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()


class MetaCache:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        db.executescript(SCHEMA)

    def get(self, key: str) -> CachedReply | None:
        row = self._db.execute("SELECT * FROM meta_cache WHERE key = ?", (key,)).fetchone()
        return None if row is None else _cached(row)

    def put(self, entry: CachedReply) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO meta_cache VALUES (?, ?, ?, ?, ?, ?)",
            (
                entry.key,
                entry.model,
                entry.reply.text,
                json.dumps(entry.reply.usage),
                entry.usd,
                _now(),
            ),
        )

    def entries(self) -> Iterator[CachedReply]:
        for row in self._db.execute("SELECT * FROM meta_cache ORDER BY created_at"):
            yield _cached(row)

    def upload_id(self, sha256: str) -> str | None:
        row = self._db.execute(
            "SELECT file_id FROM meta_uploads WHERE sha256 = ?", (sha256,)
        ).fetchone()
        return None if row is None else str(row["file_id"])

    def remember_upload(self, sha256: str, file_id: str) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO meta_uploads VALUES (?, ?, ?)", (sha256, file_id, _now())
        )

    def forget_upload(self, sha256: str) -> None:
        self._db.execute("DELETE FROM meta_uploads WHERE sha256 = ?", (sha256,))


def _cached(row: sqlite3.Row) -> CachedReply:
    usage = {str(k): int(v) for k, v in json.loads(row["usage"]).items()}
    return CachedReply(row["key"], row["model"], Reply(row["text"], usage), float(row["usd"]))
