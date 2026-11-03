"""The replay transport, watched: what reaches it, so a test can assert which calls were made."""

from dataclasses import dataclass, field
from pathlib import Path

from standard_motion.meta.models import MetaContent
from standard_motion.meta.replay import ReplayTransport
from standard_motion.meta.transport import Reply
from tests.meta.fakes import NoTranscribe


@dataclass
class CountingReplay(NoTranscribe):
    """The replay transport, counting every call that reaches it, naming each response's format
    and keeping each compile request's text."""

    replay: ReplayTransport
    calls: int = 0
    formats: list[str] = field(default_factory=list[str])  # e.g. "rubric", "reason"
    compiles: list[list[str]] = field(default_factory=list[list[str]])

    async def upload(self, path: Path) -> str:
        self.calls += 1
        return await self.replay.upload(path)

    async def count_tokens(self, model: str, content: MetaContent) -> int:
        self.calls += 1
        return await self.replay.count_tokens(model, content)

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        self.calls += 1
        text_format = options.get("text")
        name = "sam"  # SAM is asked with no text format
        if isinstance(text_format, dict):
            name = str(text_format["format"]["name"])  # pyright: ignore[reportUnknownArgumentType]
        self.formats.append(name)
        if name == "rubric":
            self.compiles.append([str(part["text"]) for part in content if "text" in part])
        return await self.replay.respond(model, content, options)
