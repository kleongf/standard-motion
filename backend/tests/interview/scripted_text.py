"""A scripted Spark for free-text interview answers: the compile calls as `ScriptedCompile`, and
the calls that read the curator's text from their own script."""

import json
from dataclasses import dataclass, field

from tests.rubric.scripted import USAGE, ScriptedCompile
from winnow.interview.text_prompt import MAPPING_SCHEMA_NAME, REWRITE_SCHEMA_NAME
from winnow.meta.models import MetaContent
from winnow.meta.transport import Reply

TEXT_FORMATS = (MAPPING_SCHEMA_NAME, REWRITE_SCHEMA_NAME)


@dataclass
class ScriptedText(ScriptedCompile):
    texts: list[object] = field(default_factory=list[object])  # a dict is sent as JSON
    read: list[str] = field(default_factory=list[str])  # each text call's prompt
    formats: list[str] = field(default_factory=list[str])  # every Spark call's format, in order

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        text_format = options.get("text")
        name = "sam"  # SAM is asked with no text format
        if isinstance(text_format, dict):
            name = str(text_format["format"]["name"])  # pyright: ignore[reportUnknownArgumentType]
        self.formats.append(name)
        if name not in TEXT_FORMATS:
            return await super().respond(model, content, options)
        self.read.append("\n".join(str(part["text"]) for part in content if "text" in part))
        answer = self.texts.pop(0)
        return Reply(answer if isinstance(answer, str) else json.dumps(answer), USAGE)
