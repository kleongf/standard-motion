"""A scripted Spark for compile tests: answers each compile call with the next scripted answer."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from tests.meta.fakes import NoTranscribe
from winnow.meta.models import MetaContent
from winnow.meta.transport import Reply

USAGE = {"input_tokens": 6000, "output_tokens": 2000}


def criterion(
    primitive: str, comparator: str, threshold: float, **fields: object
) -> dict[str, object]:
    """A Criterion as Spark writes one, with the catalog's params all null unless given."""
    given = fields.pop("params", {})
    assert isinstance(given, dict)
    params = {"speed_below_m_s": None} | cast(dict[str, object], given)
    answer: dict[str, object] = {
        "primitive": primitive,
        "params": params,
        "comparator": comparator,
        "threshold": threshold,
        "window": {"kind": "whole", "seconds": None},
        "views": [],
        "question": None,
        "paraphrases": [],
        "hard": True,
        "assumptions": [],
    }
    return answer | fields


def video_criterion(question: str, paraphrases: list[str]) -> dict[str, object]:
    """An `ask_video` Criterion as Spark writes one: the whole first exterior view after the
    release, asked `question` and its paraphrases."""
    asked: dict[str, object] = {
        "window": {"kind": "after_release", "seconds": None},
        "views": ["exterior_image_1_left"],
        "question": question,
        "paraphrases": paraphrases,
        "crop": "view",
    }
    return criterion("ask_video", ">=", 3, **asked)


def phrase(
    text: str,
    status: str = "checked",
    criteria: list[dict[str, object]] | None = None,
    reason: str | None = None,
) -> dict[str, object]:
    return {
        "phrase": text,
        "restatement": f"Precisely: {text}.",
        "status": status,
        "status_reason": reason,
        "typed_criteria": criteria or [],
    }


@dataclass
class ScriptedCompile(NoTranscribe):
    answers: list[object]  # a dict is sent as JSON, a str as is
    prompts: list[list[str]] = field(default_factory=list[list[str]])  # each call's text parts
    while_reading: Callable[[], object] | None = None  # runs during the next compile call, once

    async def upload(self, path: Path) -> str:
        return path.name

    async def count_tokens(self, model: str, content: MetaContent) -> int:
        return 6000

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        text_format = options.get("text")
        if not isinstance(text_format, dict) or text_format["format"]["name"] != "rubric":
            return Reply("", USAGE)  # ingest's Meta steps find nothing
        self.prompts.append([str(part["text"]) for part in content if "text" in part])
        answer = self.answers.pop(0)
        if self.while_reading is not None:
            act, self.while_reading = self.while_reading, None
            act()
        return Reply(answer if isinstance(answer, str) else json.dumps(answer), USAGE)
