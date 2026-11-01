"""Bisecting an assumed threshold over the anchor pool, with no model call.

The first question asks about the anchor Episode nearest the assumed threshold; each answer
narrows the stretch where the line can be (fine on one side of the closest fine Episode, not
fine past the closest not-fine one), and the next question asks about the median Episode left
inside it. At most three questions per threshold.

Then: answers on both sides put the threshold midway between the closest fine and not-fine
Episodes, with their gap as its margin (the interview gap of the plan's effective margin).
Answers all on one side that the assumed threshold already sorts right confirm it;
answers all on one side that it sorts wrong leave it unbracketed, since no anchor Episode shows
where the line is (their labels still hold).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

MAX_QUESTIONS = 3

Outcome = Literal["set", "confirmed", "unbracketed"]


@dataclass(frozen=True)
class Point:
    """One anchor Episode's measured value on the Criterion."""

    episode_id: str
    value: float


@dataclass(frozen=True)
class Answered:
    episode_id: str
    value: float
    fine: bool  # the curator's answer: True passes the Phrase


@dataclass(frozen=True)
class Resolution:
    outcome: Outcome
    threshold: float
    margin: float | None  # None: unchanged


def _sign(comparator: str) -> int:
    """+1 when small values pass, -1 when large ones do; 0 for `==`, which isn't bisected."""
    return {"<": 1, "<=": 1, ">": -1, ">=": -1}.get(comparator, 0)


@dataclass(frozen=True)
class _Bracket:
    """In passing-side coordinates (value times sign, so smaller is finer): the closest fine and
    not-fine answers."""

    fine: float | None
    not_fine: float | None

    def inside(self, x: float) -> bool:
        above = self.fine is None or x > self.fine
        below = self.not_fine is None or x < self.not_fine
        return above and below


def _bracket(asked: Sequence[Answered], sign: int) -> _Bracket:
    fine = [a.value * sign for a in asked if a.fine]
    not_fine = [a.value * sign for a in asked if not a.fine]
    return _Bracket(max(fine, default=None), min(not_fine, default=None))


def next_point(
    points: Sequence[Point], asked: Sequence[Answered], threshold: float, comparator: str
) -> Point | None:
    """The anchor Episode to ask about next, or None when the threshold is settled."""
    sign = _sign(comparator)
    if sign == 0 or len(asked) >= MAX_QUESTIONS:
        return None
    done = {a.episode_id for a in asked}
    bracket = _bracket(asked, sign)
    left = sorted(
        (p for p in points if p.episode_id not in done and bracket.inside(p.value * sign)),
        key=lambda p: p.value,
    )
    if not left:
        return None
    if not asked:
        return min(left, key=lambda p: abs(p.value - threshold))
    return left[len(left) // 2]


def _passes(value: float, threshold: float, comparator: str) -> bool:
    inclusive = comparator in ("<=", ">=")
    distance = (threshold - value) * _sign(comparator)
    return distance > 0 or (inclusive and distance == 0)


def _sorted_right(asked: Sequence[Answered], threshold: float, comparator: str) -> bool:
    """Whether the threshold already passes every fine answer and fails every other one."""
    return all(_passes(a.value, threshold, comparator) == a.fine for a in asked)


def separated(asked: Sequence[Answered], comparator: str) -> bool:
    """Whether some threshold passes every fine answer and fails every other one: the closest
    fine answer lies strictly on the passing side of the closest not-fine one. Bisection only
    asks inside the bracket, so its answers always are; labels given elsewhere can overlap."""
    bracket = _bracket(asked, _sign(comparator))
    return bracket.fine is None or bracket.not_fine is None or bracket.fine < bracket.not_fine


def resolve(asked: Sequence[Answered], threshold: float, comparator: str) -> Resolution:
    sign = _sign(comparator)
    bracket = _bracket(asked, sign)
    if bracket.fine is not None and bracket.not_fine is not None:
        middle = (bracket.fine + bracket.not_fine) / 2 * sign
        gap = abs(bracket.not_fine - bracket.fine)
        return Resolution("set", round(middle, 6), round(gap, 6))
    if _sorted_right(asked, threshold, comparator):
        return Resolution("confirmed", threshold, None)
    return Resolution("unbracketed", threshold, None)
