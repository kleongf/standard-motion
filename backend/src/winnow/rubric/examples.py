"""The few-shot examples compile shows Spark: Descriptions with the answer each should get.

Written against the catalog's measured primitives only, so they stay valid as tracked and visual
primitives join; a test checks every example passes the same checks Spark's answers do.
"""

from dataclasses import dataclass

from winnow.criteria.primitives import PRIMITIVES


@dataclass(frozen=True)
class Example:
    description: str
    answer: dict[str, object]


def _criterion(
    primitive: str,
    comparator: str,
    threshold: float,
    *,
    window: str = "whole",
    params: dict[str, float] | None = None,
    assumptions: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "primitive": primitive,
        "params": {name: None for info in PRIMITIVES.values() for name in info.params}
        | (params or {}),
        "comparator": comparator,
        "threshold": threshold,
        "window": {"kind": window, "seconds": None},
        "views": [],
        "question": None,
        "paraphrases": [],
        "crop": None,
        "hard": True,
        "assumptions": list(assumptions),
    }


def _phrase(
    text: str,
    restatement: str,
    status: str,
    criteria: list[dict[str, object]] | None = None,
    reason: str | None = None,
) -> dict[str, object]:
    return {
        "phrase": text,
        "restatement": restatement,
        "status": status,
        "status_reason": reason,
        "typed_criteria": criteria or [],
    }


EXAMPLES = (
    Example(
        "A clean pick: picks up the cup in a single grasp, carries it without stopping, and "
        "ideally takes a direct path.",
        {
            "phrases": [
                _phrase(
                    "A clean pick",
                    "Names the kind of Episode wanted; the Phrases after it say what clean means.",
                    "context",
                    reason="Frames the Description; it asks nothing of an Episode by itself.",
                ),
                _phrase(
                    "picks up the cup in a single grasp",
                    "The first closure of the gripper is the grasp that lifts the cup: no failed "
                    "attempts before it.",
                    "checked",
                    [_criterion("grasp_attempts", "<=", 1)],
                ),
                _phrase(
                    "carries it without stopping",
                    "While the cup is held, the arm never stands still for a noticeable time.",
                    "checked",
                    [
                        _criterion(
                            "longest_still_s",
                            "<",
                            1.0,
                            window="holding",
                            params={"speed_below_m_s": 0.01},
                            assumptions=(
                                "Stopping means the arm under 1 cm/s for 1 s or more while "
                                "holding.",
                            ),
                        )
                    ],
                ),
                _phrase(
                    "ideally takes a direct path",
                    "Preferably the end effector travels close to a straight line; this never "
                    "rejects an Episode on its own.",
                    "checked",
                    [
                        _criterion(
                            "path_efficiency",
                            ">=",
                            0.6,
                            assumptions=("Direct: a straight line is at least 60% of the path.",),
                        )
                        | {"hard": False}
                    ],
                ),
            ]
        },
    ),
    Example(
        "Finishes within 20 seconds of moving and sets the bowl down gently, without knocking "
        "anything over.",
        {
            "phrases": [
                _phrase(
                    "Finishes within 20 seconds of moving",
                    "The arm spends at most 20 s moving over the whole Episode.",
                    "checked",
                    [_criterion("active_duration_s", "<=", 20.0)],
                ),
                _phrase(
                    "sets the bowl down gently",
                    "The bowl is placed, not dropped: released close to the height it was "
                    "picked up from.",
                    "checked",
                    [
                        _criterion(
                            "release_height_m",
                            "<=",
                            0.03,
                            assumptions=(
                                "Gently: released within 3 cm above where it was picked up.",
                            ),
                        )
                    ],
                ),
                _phrase(
                    "without knocking anything over",
                    "No object other than the bowl is moved or tipped.",
                    "unsupported",
                    reason="No available primitive observes objects other than the one moved.",
                ),
            ]
        },
    ),
)
