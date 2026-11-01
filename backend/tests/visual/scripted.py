"""A scripted Spark for the visual step: each sample's answer is scripted per Episode, in prompt
order (question, then paraphrases). Everything else goes to the scripted SAM and baseline."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from tests.interview.scripted_text import TEXT_FORMATS, ScriptedText
from tests.meta.fakes import NoTranscribe
from tests.tracking.scripted_sam import ScriptedSam
from winnow.meta.models import MetaContent
from winnow.meta.transport import Reply
from winnow.visual.models import AnswerValue

USAGE = {"input_tokens": 9000, "output_tokens": 300}


@dataclass(frozen=True)
class VisualCall:
    prompt: str
    clip: str  # e.g. "000000/visual/0123456789abcdef.mp4"


@dataclass
class ScriptedVisual(NoTranscribe):
    # Per Episode folder (e.g. "000001"), one answer per sample; "pass" from every sample else.
    answers: dict[str, tuple[AnswerValue, ...]] = field(
        default_factory=dict[str, tuple[AnswerValue, ...]]
    )
    calls: list[VisualCall] = field(default_factory=list[VisualCall])
    sam: ScriptedSam = field(default_factory=ScriptedSam)

    async def upload(self, path: Path) -> str:
        return "/".join(path.parts[-3:])

    async def count_tokens(self, model: str, content: MetaContent) -> int:
        return 1000

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        text_format = options.get("text")
        if not isinstance(text_format, dict) or text_format["format"]["name"] != "visual":
            return await self.sam.respond(model, content, options)
        prompt, clip = str(content[0]["text"]), str(content[1]["file_id"])
        sample = sum(1 for c in self.calls if c.clip == clip)
        self.calls.append(VisualCall(prompt, clip))
        scripted = self.answers.get(clip.split("/")[0], ("pass",) * 3)
        answer = {
            "answer": scripted[sample % len(scripted)],
            "confidence": 0.8,
            "observation": f"The marker rests in the pot (sample {sample + 1}).",
        }
        return Reply(json.dumps(answer), USAGE)


@dataclass
class CompileAndAsk(NoTranscribe):
    """Scripted compile answers and readings of the curator's words, and scripted visual answers
    to whatever is asked."""

    compile: ScriptedText
    visual: ScriptedVisual

    async def upload(self, path: Path) -> str:
        return await self.visual.upload(path)

    async def count_tokens(self, model: str, content: MetaContent) -> int:
        return 1000

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        if response_format(options) in ("rubric", *TEXT_FORMATS):
            return await self.compile.respond(model, content, options)
        return await self.visual.respond(model, content, options)


def response_format(options: dict[str, object]) -> str | None:
    """The name of the structured answer a Spark call asks for; None for SAM's calls."""
    text_format = options.get("text")
    if not isinstance(text_format, dict):
        return None
    return str(text_format["format"]["name"])  # pyright: ignore[reportUnknownArgumentType]
