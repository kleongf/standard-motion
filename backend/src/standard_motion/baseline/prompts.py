"""Spark alone: the holistic judge Standard Motion is compared against (evaluation protocol, #10).

Same tier, all three views as native video, the Description plus the instruction, and a
structured answer, so the comparison is fair. The FailBench check asks only "did it succeed?".
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Description:
    text: str
    phrases: tuple[str, ...]  # what a failure type may name, besides "other"


# The one frozen Description that Reference labels and the evaluation use.
FROZEN = Description(
    "Expert pick-and-place: grasps the object on the first try, never drops it, places it in "
    "or on the target named in the instruction, no long pauses.",
    (
        "grasps the object on the first try",
        "never drops it",
        "places it in or on the target named in the instruction",
        "no long pauses",
    ),
)
FROZEN_DESCRIPTION = FROZEN.text

VIEWS = "3 cameras (exterior 1, exterior 2, wrist)"


def _task(instruction: str | None) -> str:
    if instruction:
        return f"The robot's task: {instruction}."
    return "The robot's task wasn't recorded; infer it from the video."


def baseline_prompt(description: Description, instruction: str | None) -> str:
    phrases = ", ".join(f'"{p}"' for p in description.phrases)
    return (
        f"These are synchronized recordings of one robot attempt from {VIEWS}. "
        f"{_task(instruction)}\n\n"
        "A team keeps only recordings that meet this description of an expert attempt:\n"
        f'"{description.text}"\n\n'
        "Decide whether this attempt meets the description: keep it or reject it. If you reject "
        f'it, name the part of the description it fails (one of {phrases}, or "other") and '
        "the time in seconds where it first fails. Give a one-sentence reason, and your "
        "confidence from 0 to 1 that your decision is right."
    )


def baseline_schema(description: Description) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["decision", "failure_type", "time_s", "reason", "confidence"],
        "properties": {
            "decision": {"type": "string", "enum": ["keep", "reject"]},
            "failure_type": {
                "type": ["string", "null"],
                "enum": [*description.phrases, "other", None],
            },
            "time_s": {"type": ["number", "null"]},
            "reason": {"type": "string"},
            "confidence": {"type": "number"},
        },
    }


def failbench_prompt(instruction: str | None) -> str:
    return (
        f"These are synchronized recordings of one robot attempt from {VIEWS}. "
        f"{_task(instruction)} Did the robot complete the task successfully? Give your "
        "confidence from 0 to 1."
    )


FAILBENCH_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["success", "confidence"],
    "properties": {"success": {"type": "boolean"}, "confidence": {"type": "number"}},
}
