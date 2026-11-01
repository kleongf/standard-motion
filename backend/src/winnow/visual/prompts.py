"""The words of one visual sample: the Episode's task, then one frozen prompt about the clip."""

from typing import get_args

from winnow.visual.models import AnswerValue, VisualClip

VISUAL_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer", "confidence", "observation"],
    "properties": {
        "answer": {"type": "string", "enum": list(get_args(AnswerValue))},
        "confidence": {"type": "number"},
        "observation": {"type": "string"},
    },
}


def _task(instruction: str | None) -> str:
    if instruction:
        return f"The robot's task: {instruction}."
    return "The robot's task wasn't recorded; infer it from the clip."


def visual_prompt(prompt: str, instruction: str | None, clip: VisualClip) -> str:
    framing = "cropped to the object and its target" if clip.box else "the whole camera view"
    return (
        f"This short clip is one robot attempt, from {clip.start:.1f} s to {clip.end:.1f} s of "
        f"the recording, {framing}. {_task(instruction)}\n\n"
        f"Question: {prompt}\n\n"
        'Answer "pass" if the answer is yes, "fail" if it is no, and "unsure" if the clip '
        "doesn't show enough to tell. Say in one sentence what you saw that decides it, and "
        "give your confidence from 0 to 1."
    )
