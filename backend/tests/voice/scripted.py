"""A scripted Meta API for voice turns: Voice Transcribe hears `said`, and Spark maps it onto
Phrases as scripted in `marks`. Everything else goes to the scripted visual Spark and SAM."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from standard_motion.meta.models import MetaContent, Transcript, Turn
from standard_motion.meta.transport import Reply
from tests.meta.test_transcribe_transport import transport_answering
from tests.visual.scripted import ScriptedVisual

USAGE = {"input_tokens": 600, "output_tokens": 80}


@dataclass
class ScriptedVoice(ScriptedVisual):
    said: str = "It drops the marker right here, before the pot."
    # What Spark answers about the transcript: each Phrase it decides, as pass or fail.
    marks: list[dict[str, str]] = field(default_factory=list[dict[str, str]])
    answer: str | None = None  # a raw answer, in place of `marks`
    # Meta's own TranscribeResponse body, read by the real transport, in place of `said`.
    reply: dict[str, object] | bytes | None = None
    transcribed: list[Path] = field(default_factory=list[Path])
    asked: list[str] = field(default_factory=list[str])  # the voice prompts Spark was sent

    async def transcribe(self, model: str, audio: Path, options: dict[str, object]) -> Transcript:
        self.transcribed.append(audio)
        if self.reply is not None:
            return await transport_answering(200, self.reply, []).transcribe(model, audio, options)
        return Transcript(turns=(Turn(text=self.said, start_ms=0, end_ms=2300),))

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        text_format = options.get("text")
        if not isinstance(text_format, dict) or text_format["format"]["name"] != "voice":
            return await super().respond(model, content, options)
        self.asked.append(str(content[0]["text"]))
        answer = self.answer if self.answer is not None else json.dumps({"phrases": self.marks})
        return Reply(answer, USAGE)
