"""The quality score: how an Episode compares with the rest of its run on the soft Criteria.

Each soft Criterion's value is oriented so that higher is better (its signed distance to the
threshold), then turned into a robust z within the run: (o - median) / (1.4826 * MAD). An
Episode's quality is the mean of its z's. It is relative to the run and never decides anything.
"""

from collections import defaultdict
from collections.abc import Sequence
from statistics import mean, median

from winnow.criteria.comparison import signed_distance
from winnow.triage.models import Triage

MAD_TO_SD = 1.4826  # scales the MAD to a standard deviation for normal data


def qualities(triages: Sequence[Triage]) -> list[float | None]:
    """Each Triage's quality within `triages`, or None when it has no soft value to compare."""
    oriented: dict[str, dict[int, float]] = defaultdict(dict)  # Criterion -> Episode -> value
    for i, triage in enumerate(triages):
        for result in triage.criteria:
            if not result.hard and result.value is not None:
                oriented[result.criterion_id][i] = signed_distance(result, result.value)
    zs: list[list[float]] = [[] for _ in triages]
    for values in oriented.values():
        middle = median(values.values())
        mad = median(abs(v - middle) for v in values.values())
        if mad == 0:  # most of the run is alike: it can't tell them apart
            continue
        for i, v in values.items():
            zs[i].append((v - middle) / (MAD_TO_SD * mad))
    return [mean(z) if z else None for z in zs]
