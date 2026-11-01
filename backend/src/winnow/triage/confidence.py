"""How sure each result is: a Criterion's status, Uncertainty signal and p_pass, then a Phrase's
p, P_keep and the Episode's confidence.

p = 1/(1 + e^(-3m)), with m the signed distance from the threshold in effective margins
(effective margin = max(noise floor, interview gap) * s). A measurement within one effective
margin of its threshold is unsure ("near threshold"); an inconclusive primitive never pulls p
below 0.5; no value gives 0.5; a human label gives 1 or 0.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from winnow.criteria.comparison import passes, signed_distance
from winnow.criteria.measured import Measurement
from winnow.criteria.models import Criterion, Status, UncertaintySignal
from winnow.criteria.primitives import PRIMITIVES

# The margin multiplier s until calibration tunes it on the Dev set's labels (`calibration`); a new
# Rubric version starts here.
UNCALIBRATED = 1.0
STEEPNESS = 3.0


@dataclass(frozen=True)
class Judgement:
    status: Status
    uncertainty: UncertaintySignal | None
    p_pass: float


def p_of(m: float) -> float:
    """1 or 0 for a crisp result with no margin (m = ±inf)."""
    if math.isinf(m):
        return 1.0 if m > 0 else 0.0
    return 1 / (1 + math.exp(-STEEPNESS * max(-100.0, min(100.0, m))))


def effective_margin(criterion: Criterion, s: float = UNCALIBRATED) -> float:
    return max(PRIMITIVES[criterion.primitive].noise_floor, criterion.margin) * s


def _crisp_m(status: Status) -> float | None:
    return {"pass": math.inf, "fail": -math.inf, "unsure": None}[status]


def _read(
    criterion: Criterion, measured: Measurement, s: float
) -> tuple[Status, UncertaintySignal | None, float | None]:
    """(status, signal, m) before an inconclusive primitive's clamp; m None means no value."""
    if measured.uncertainty is not None:  # the measure knows why it is unsure
        return measured.status or "unsure", measured.uncertainty, measured.m
    if measured.value is None:
        return "unsure", "source missing", None
    if measured.status is not None:  # decided whatever the threshold, e.g. no grasp
        return measured.status, None, _crisp_m(measured.status)
    margin = effective_margin(criterion, s)
    distance = signed_distance(criterion, measured.value)
    passed = passes(criterion, measured.value)
    if margin > 0 and abs(distance) < margin:
        return "unsure", "near threshold", distance / margin
    if margin > 0:
        return ("pass" if passed else "fail"), None, distance / margin
    return ("pass" if passed else "fail"), None, math.inf if passed else -math.inf


def judge(criterion: Criterion, measured: Measurement, s: float = UNCALIBRATED) -> Judgement:
    status, signal, m = _read(criterion, measured, s)
    from_m = 0.5 if m is None else p_of(m)
    # The measure may know p directly, e.g. Spark's agreement.
    p = from_m if measured.p is None else measured.p
    if not PRIMITIVES[criterion.primitive].conclusive:
        p = max(p, 0.5)
        if status == "fail" and signal is None:
            signal = "unconfirmed fail"
    return Judgement(status, signal, p)


def phrase_p(p_values: Sequence[float]) -> float | None:
    """A Phrase is as sure as its least sure Criterion; None when nothing checks it."""
    return min(p_values) if p_values else None


def p_keep(phrase_ps: Sequence[float | None]) -> float:
    """The min over hard Phrases' p; 1 when no hard Phrase is checked."""
    return min((p for p in phrase_ps if p is not None), default=1.0)


def confidence(keep: float) -> float:
    return max(keep, 1 - keep)
