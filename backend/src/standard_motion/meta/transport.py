"""The network edge of `meta/`: everything above it is testable without the Meta API."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from standard_motion.meta.models import MetaContent, Transcript


@dataclass(frozen=True)
class Reply:
    text: str
    usage: dict[str, int]  # input_tokens, output_tokens, cached_tokens, video_frames_processed
    incomplete: str | None = None  # why the model stopped early, e.g. "max_output_tokens"


class TransientError(RuntimeError):
    """A 429, a 5xx, or a dropped connection: worth retrying."""


class FileGoneError(RuntimeError):
    """The server no longer has a file we uploaded earlier."""


class UnusableReplyError(RuntimeError):
    """The Meta API answered, but not in a shape we can read: not worth retrying."""


class Transport(Protocol):
    async def upload(self, path: Path) -> str: ...

    async def count_tokens(self, model: str, content: MetaContent) -> int: ...

    async def respond(
        self, model: str, content: MetaContent, options: dict[str, object]
    ) -> Reply: ...

    async def transcribe(
        self, model: str, audio: Path, options: dict[str, object]
    ) -> Transcript: ...
