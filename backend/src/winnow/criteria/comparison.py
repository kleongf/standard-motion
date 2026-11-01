"""A Criterion's comparator, applied to a measured value."""

from typing import Protocol

from winnow.criteria.models import Comparator, Criterion


class Thresholded(Protocol):
    """A Criterion, or its result: anything with a comparator and a threshold."""

    @property
    def comparator(self) -> Comparator: ...

    @property
    def threshold(self) -> float: ...


def passes(criterion: Criterion, value: float) -> bool:
    match criterion.comparator:
        case "<":
            return value < criterion.threshold
        case "<=":
            return value <= criterion.threshold
        case ">=":
            return value >= criterion.threshold
        case ">":
            return value > criterion.threshold
        case "==":
            return value == criterion.threshold


def signed_distance(criterion: Thresholded, value: float) -> float:
    """How far `value` is from the threshold, in the Criterion's unit: positive on the passing
    side, negative on the failing side (always ≤ 0 for `==`)."""
    match criterion.comparator:
        case "<" | "<=":
            return criterion.threshold - value
        case ">" | ">=":
            return value - criterion.threshold
        case "==":
            return -abs(value - criterion.threshold)
