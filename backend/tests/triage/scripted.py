"""A scripted Meta API for Spark's Reasons: each Reason says "Written by Spark", citing the first
time the prompt gives (a Reject's template leads with its lead fail's), unless `answer` is
scripted. Everything else goes to the scripted visual Spark and SAM."""

import json
import re
from dataclasses import dataclass, field

from tests.visual.scripted import ScriptedVisual
from winnow.meta.models import MetaContent
from winnow.meta.transport import Reply

USAGE = {"input_tokens": 1500, "output_tokens": 60}
GIVEN = re.compile(r"\[t=([0-9.]+)\]")


def written_by_spark(prompt: str) -> list[dict[str, object]]:
    found = GIVEN.search(prompt)
    if found is None:
        return [{"text": "Written by Spark.", "t": None}]
    t = float(found.group(1))
    return [
        {"text": "Written by Spark, from ", "t": None},
        {"text": f"{t:.1f} s", "t": t},
        {"text": ".", "t": None},
    ]


@dataclass
class ScriptedReason(ScriptedVisual):
    answer: str | None = None  # a raw answer, in place of the default one
    asked: list[str] = field(default_factory=list[str])  # the Reason prompts Spark was sent

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        text_format = options.get("text")
        if not isinstance(text_format, dict) or text_format["format"]["name"] != "reason":
            return await super().respond(model, content, options)
        prompt = str(content[0]["text"])
        self.asked.append(prompt)
        answer = self.answer or json.dumps({"spans": written_by_spark(prompt)})
        return Reply(answer, USAGE)
