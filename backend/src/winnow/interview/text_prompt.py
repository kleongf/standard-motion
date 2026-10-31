"""The words of the Spark calls that read the curator's own words in the interview: one maps them
onto the question being asked, the other edits the Description with them."""

import json
from collections.abc import Sequence

from winnow.interview.models import (
    DisagreeQuestion,
    HardSoftQuestion,
    PhraseQuestion,
    Question,
    SettingQuestion,
    ThresholdQuestion,
)

MAPPING_SCHEMA_NAME = "interview_text"
REWRITE_SCHEMA_NAME = "description_rewrite"
CHANGE = "change"  # compile the asked text again, read with the curator's words
NONE = "none"  # the words answer nothing asked
_REPLY = 'In "reply", say back to the curator, in one short sentence, what you understood.'


def mapping_schema(choices: Sequence[str]) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["choice", "reply"],
        "properties": {
            "choice": {"type": "string", "enum": list(choices)},
            "reply": {"type": "string"},
        },
    }


def _about(question: Question) -> str:
    match question:
        case PhraseQuestion(kind="phrase"):
            return f"It is about the Phrase {json.dumps(question.text)}."
        case PhraseQuestion():
            return f"It is about the words {json.dumps(question.text)}, which are in no Phrase."
        case ThresholdQuestion() | HardSoftQuestion():
            return (
                f"It is about the Phrase {json.dumps(question.phrase)}, which the Criterion "
                f"{json.dumps(question.english)} checks."
            )
        case SettingQuestion():
            return f"It is about the setting {json.dumps(question.name)} on one Episode."
        case DisagreeQuestion():
            return f"It is about the Phrase {json.dumps(question.phrase)} on one Episode."


def mapping_prompt(question: Question, text: str, subject: str | None) -> str:
    """`subject` is the text a "change" answer compiles again; None when it can't be asked."""
    options = "\n".join(f"- {json.dumps(o.answer)}: {o.label}" for o in question.options)
    change = ""
    if subject is not None:
        change = (
            f'Answer "{CHANGE}" if their words instead say what {json.dumps(subject)} should '
            "require, so that it should be compiled again, read as they say. "
        )
    return f"""A curator is describing what a good robot Episode looks like, and Winnow is \
asking them about their Description. It asked:
{json.dumps(question.prompt)}
{_about(question)}

The answers it offers:
{options}

The curator answered in their own words:
{json.dumps(text)}

Answer with the offered answer their words mean. {change}Answer "{NONE}" if their words mean \
none of these. {_REPLY}"""


REWRITE_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["description", "reply"],
    "properties": {"description": {"type": "string"}, "reply": {"type": "string"}},
}


def rewrite_prompt(description: str, text: str) -> str:
    return f"""A curator's Description of what a good robot Episode looks like:
{json.dumps(description)}

They asked for a change to it, in their own words:
{json.dumps(text)}

Give the Description with that change made ("description"), changing as little as you can: keep \
every other word as it is, character for character, so what they didn't ask about stays \
compiled as it is. If their words ask for no change, give the Description back unchanged. \
{_REPLY}"""
