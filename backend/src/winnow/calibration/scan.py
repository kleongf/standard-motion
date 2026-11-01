"""The margin-multiplier scan and its leave-one-out check, over labelled (Episode, Phrase) pairs.
Pure: the service scores the Episodes and turns each pair into a Pattern.

The grid is pre-registered and scanned widest first, keeping the last s whose errors have a
one-sided Clopper–Pearson upper bound ≤ MAX_ERROR_RATE at CONFIDENCE. An error is a crisp Phrase
result its label contradicts; an unsure one is never an error, but its pair still counts in n.
When even the widest s misses the bound, s stays at the widest and the scan says so.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations_with_replacement

from winnow.evaluation.stats import clopper_pearson_upper

GRID = (2.0, 1.5, 1.0, 0.75, 0.5)
MAX_ERROR_RATE = 0.2
CONFIDENCE = 0.9
DROPPED = 2  # the leave-one-out check drops this many labels at a time

# One labelled pair: whether its label contradicts its crisp Phrase result at each s of GRID.
type Pattern = tuple[bool, ...]


@dataclass(frozen=True)
class Scan:
    s: float
    bound_met: bool  # False: no s met the bound, so s is the widest
    n: int  # labelled pairs
    errors: int  # at s


def _pick(errors: Sequence[int], n: int) -> tuple[float, bool]:
    """The last s, widest first, whose `errors` (by GRID index) keep the bound."""
    chosen: float | None = None
    for s, wrong in zip(GRID, errors, strict=True):
        if clopper_pearson_upper(wrong, n, CONFIDENCE) > MAX_ERROR_RATE:
            break
        chosen = s
    return (GRID[0], False) if chosen is None else (chosen, True)


def _errors(pairs: Sequence[Pattern]) -> list[int]:
    return [sum(p[i] for p in pairs) for i in range(len(GRID))]


def scan(pairs: Sequence[Pattern]) -> Scan:
    errors = _errors(pairs)
    s, met = _pick(errors, len(pairs))
    return Scan(s=s, bound_met=met, n=len(pairs), errors=errors[GRID.index(s)])


def unstable(pairs: Sequence[Pattern]) -> bool:
    """Whether dropping some 2 labels moves s. Every pair of labels is checked: dropping two
    labels with the same Patterns as two others changes the scan the same way, so it is enough
    to try each pair of distinct Patterns (at most 32 of them), however many labels there are."""
    n = len(pairs)
    if n < DROPPED:
        return False
    chosen = scan(pairs).s
    totals = _errors(pairs)
    counts = Counter(pairs)
    for a, b in combinations_with_replacement(counts, DROPPED):
        if a == b and counts[a] < DROPPED:
            continue
        left = [t - x - y for t, x, y in zip(totals, a, b, strict=True)]
        if _pick(left, n - DROPPED)[0] != chosen:
            return True
    return False
