"""Recorded Meta responses for tests and CI, which never call the Meta API.

Two ways to replay:

- `export_recordings` the cache to a file, then `load_recordings` it into a fresh cache and use
  `OfflineTransport`: a recorded request is a cache hit and anything else fails loudly. The cache
  keys clips by content, so this only replays on the machine whose ffmpeg encoded them.
- Record through `RecordingTransport`, then serve with `ReplayTransport`. These match a request
  by model, text, options and each clip's path under the data dir, not its bytes: encoders stamp
  their version into every clip, so CI's ffmpeg never reproduces a local clip byte for byte. The
  real `meta/` code (cache, limiter, cost log) still runs on top.
"""

import hashlib
import json
import sqlite3
from pathlib import Path

from winnow.meta.audio import parse_transcript, transcript_json
from winnow.meta.cache import CachedReply, MetaCache
from winnow.meta.models import MetaContent, Transcript
from winnow.meta.transport import Reply, Transport


class UnrecordedCallError(RuntimeError):
    pass


# The browser captures each turn live, so no two turns' audio match byte for byte: a recorded
# transcript is keyed by model and options alone, and answers any audio.
ANY_AUDIO: MetaContent = [{"type": "input_audio"}]


def _unrecorded(model: str, content: MetaContent) -> UnrecordedCallError:
    texts = [str(part["text"])[:200] for part in content if part.get("type") == "input_text"]
    return UnrecordedCallError(
        f"No recorded {model} response for {texts}. Make the call for real once and record it "
        "(see winnow.meta.replay)."
    )


class OfflineTransport:
    async def upload(self, path: Path) -> str:
        raise UnrecordedCallError(f"Upload of {path.name} attempted offline")

    async def count_tokens(self, model: str, content: MetaContent) -> int:
        raise _unrecorded(model, content)

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        raise _unrecorded(model, content)

    async def transcribe(self, model: str, audio: Path, options: dict[str, object]) -> Transcript:
        raise _unrecorded(model, ANY_AUDIO)


def export_recordings(db: sqlite3.Connection, path: Path) -> int:
    """Write every cached response as one JSON line; returns how many."""
    entries = list(MetaCache(db).entries())
    lines = [
        json.dumps(
            {
                "key": e.key,
                "model": e.model,
                "text": e.reply.text,
                "usage": e.reply.usage,
                "usd": e.usd,
            }
        )
        for e in entries
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(line + "\n" for line in lines))
    return len(lines)


def load_recordings(db: sqlite3.Connection, path: Path) -> int:
    cache = MetaCache(db)
    count = 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        usage = {str(k): int(v) for k, v in row["usage"].items()}
        reply = Reply(str(row["text"]), usage)
        cache.put(CachedReply(str(row["key"]), str(row["model"]), reply, float(row["usd"])))
        count += 1
    return count


def _clip_name(path: Path) -> str:
    """Stable across machines and data dirs: e.g. droid_100/000001/wrist_image_left.5fps.mp4."""
    return "/".join(path.parts[-3:])


def _replay_key(model: str, content: MetaContent, options: dict[str, object]) -> str:
    request = {"model": model, "content": content, "options": options}
    return hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()


class RecordingTransport:
    """Passes calls through to the real transport and appends each reply to `path`."""

    def __init__(self, inner: Transport, path: Path) -> None:
        self._inner = inner
        self._path = path
        self._names: dict[str, str] = {}  # real file id -> clip name

    async def upload(self, path: Path) -> str:
        file_id = await self._inner.upload(path)
        self._names[file_id] = _clip_name(path)
        return file_id

    async def count_tokens(self, model: str, content: MetaContent) -> int:
        return await self._inner.count_tokens(model, content)

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        reply = await self._inner.respond(model, content, options)
        portable = [
            {**part, "file_id": self._names[str(part["file_id"])]} if "file_id" in part else part
            for part in content
        ]
        self._write(_replay_key(model, portable, options), model, reply)
        return reply

    async def transcribe(self, model: str, audio: Path, options: dict[str, object]) -> Transcript:
        transcript = await self._inner.transcribe(model, audio, options)
        reply = Reply(transcript_json(transcript), {})
        self._write(_replay_key(model, ANY_AUDIO, options), model, reply)
        return transcript

    def _write(self, key: str, model: str, reply: Reply) -> None:
        row = {"key": key, "model": model}
        row |= {"text": reply.text, "usage": reply.usage, "incomplete": reply.incomplete}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a") as out:
            out.write(json.dumps(row) + "\n")


class ReplayTransport:
    """Serves replies `RecordingTransport` recorded; anything else fails loudly."""

    def __init__(self, path: Path) -> None:
        self._replies: dict[str, Reply] = {}
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                usage = {str(k): int(v) for k, v in row["usage"].items()}
                self._replies[row["key"]] = Reply(row["text"], usage, row.get("incomplete"))

    async def upload(self, path: Path) -> str:
        return _clip_name(path)

    async def count_tokens(self, model: str, content: MetaContent) -> int:
        return 0  # only sizes the budget reservation; the recorded usage prices the call

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        reply = self._replies.get(_replay_key(model, content, options))
        if reply is None:
            raise _unrecorded(model, content)
        return reply

    async def transcribe(self, model: str, audio: Path, options: dict[str, object]) -> Transcript:
        reply = self._replies.get(_replay_key(model, ANY_AUDIO, options))
        if reply is None:
            raise _unrecorded(model, ANY_AUDIO)
        return parse_transcript(reply.text)
