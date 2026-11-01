"""A scripted Spark for baseline tests: canned, valid answers unless told to break one. SAM
(the wrist track ingest also runs) finds nothing."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from tests.meta.fakes import NoTranscribe
from winnow.meta.models import MetaContent
from winnow.meta.pricing import SAM
from winnow.meta.transport import Reply

REASON = "Released the object above the target at 17 s."  # unique, to spot leaks


@dataclass
class ScriptedSpark(NoTranscribe):
    malformed_calls: set[int] = field(default_factory=set[int])  # 1-based baseline call numbers
    baseline_calls: int = 0
    failbench_calls: int = 0
    prompts: list[str] = field(default_factory=list[str])

    async def upload(self, path: Path) -> str:
        return f"file-{path.parent.name}-{path.stem}"

    async def count_tokens(self, model: str, content: MetaContent) -> int:
        return 1000

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        if model == SAM:
            return Reply("", {"video_frames_processed": 15})
        text_format = options["text"]
        assert isinstance(text_format, dict)
        name = text_format["format"]["name"]  # pyright: ignore[reportUnknownVariableType]
        self.prompts.append(str(content[0]["text"]))
        usage = {"input_tokens": 3000, "output_tokens": 1500}
        if name == "failbench":
            self.failbench_calls += 1
            return Reply(json.dumps({"success": True, "confidence": 0.8}), usage)
        self.baseline_calls += 1
        if self.baseline_calls in self.malformed_calls:
            return Reply('{"decision": "keep", "reason": ', usage)  # cut off mid-answer
        answer = {
            "decision": "reject",
            "failure_type": "never drops it",
            "time_s": 17.0,
            "reason": REASON,
            "confidence": 0.7,
        }
        return Reply(json.dumps(answer), usage)
