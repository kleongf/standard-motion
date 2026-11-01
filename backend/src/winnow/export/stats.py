"""Feature stats as LeRobot keeps them: per Episode in meta/episodes' `stats/<feature>/<stat>`
columns, and for the whole dataset in meta/stats.json, combined the way LeRobot's
`aggregate_stats` combines them. Computed with numpy alone; `lerobot` is never a dependency."""

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pyarrow as pa
from numpy.typing import NDArray

QUANTILES = {"q01": 0.01, "q10": 0.10, "q50": 0.50, "q90": 0.90, "q99": 0.99}
_NEEDED = ("min", "max", "mean", "std", "count")  # without these, a feature can't be combined
_PREFIX = "stats/"


def _values(column: "pa.ChunkedArray[Any]") -> NDArray[Any] | None:
    """A column's values as (frames, dimensions), or None unless it's numeric or boolean."""
    kind: pa.DataType = column.type
    if isinstance(kind, pa.ListType | pa.LargeListType | pa.FixedSizeListType):
        kind = kind.value_type  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    numeric = pa.types.is_integer(kind) or pa.types.is_floating(kind)  # pyright: ignore[reportUnknownArgumentType]
    if not (numeric or pa.types.is_boolean(kind)) or len(column) == 0:  # pyright: ignore[reportUnknownArgumentType]
        return None
    values = np.asarray(column.to_pylist())
    return values.reshape(len(values), -1)


def episode_stats(frames: pa.Table) -> dict[str, list[Any]]:
    """meta/episodes' stats columns for one Episode's frames, one item per dimension, for every
    numeric or boolean column (LeRobot computes none for text): min and max in the column's own
    type, the rest as floats, std the population's."""
    stats: dict[str, list[Any]] = {}
    for name in frames.column_names:
        values = _values(frames.column(name))
        if values is None:
            continue
        numbers = values.astype(np.float64)
        found: dict[str, NDArray[Any]] = {
            "min": values.min(axis=0),
            "max": values.max(axis=0),
            "mean": numbers.mean(axis=0),
            "std": numbers.std(axis=0),
            "count": np.array([len(values)]),
            **{q: np.quantile(numbers, p, axis=0) for q, p in QUANTILES.items()},
        }
        stats |= {f"{_PREFIX}{name}/{stat}": value.tolist() for stat, value in found.items()}
    return stats


def _feature(row: Mapping[str, Any], feature: str) -> dict[str, NDArray[Any]] | None:
    stats = {
        stat: np.asarray(row[key])
        for stat in (*_NEEDED, *QUANTILES)
        if (key := f"{_PREFIX}{feature}/{stat}") in row and row[key] is not None
    }
    return stats if all(stat in stats for stat in _NEEDED) else None


def _combined(episodes: list[dict[str, NDArray[Any]]]) -> dict[str, list[Any]]:
    """LeRobot's aggregate_feature_stats: the count-weighted mean; the pooled std (each
    Episode's variance plus its mean's squared distance from the whole's, weighted by count);
    min of mins, max of maxes, the summed count. Quantiles can't be pooled exactly from
    per-Episode quantiles, so like LeRobot this takes their count-weighted mean, an
    approximation of the whole's: the export's stats.json matches what LeRobot itself would
    write for the same Episodes."""
    means = np.stack([e["mean"] for e in episodes]).astype(np.float64)
    counts = np.stack([e["count"] for e in episodes])
    total = counts.sum(axis=0)
    weights = counts.reshape(counts.shape + (1,) * (means.ndim - counts.ndim))
    mean = (means * weights).sum(axis=0) / total
    variances = np.stack([e["std"] for e in episodes]).astype(np.float64) ** 2
    variance = ((variances + (means - mean) ** 2) * weights).sum(axis=0) / total
    combined: dict[str, NDArray[Any]] = {
        "min": np.min(np.stack([e["min"] for e in episodes]), axis=0),
        "max": np.max(np.stack([e["max"] for e in episodes]), axis=0),
        "mean": mean,
        "std": np.sqrt(variance),
        "count": total,
    }
    for q in QUANTILES:
        if all(q in e for e in episodes):
            quantiles = np.stack([e[q] for e in episodes]).astype(np.float64)
            combined[q] = (quantiles * weights).sum(axis=0) / total
    return {stat: value.tolist() for stat, value in combined.items()}


def aggregate_stats(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, list[Any]]]:
    """meta/stats.json from the exported meta/episodes rows: each feature whose min, max, mean,
    std and count every row has, combined over the rows."""
    features = sorted(
        {
            key.removeprefix(_PREFIX).rsplit("/", 1)[0]
            for row in rows
            for key in row
            if key.startswith(_PREFIX)
        }
    )
    aggregated: dict[str, dict[str, list[Any]]] = {}
    for feature in features:
        episodes = [_feature(row, feature) for row in rows]
        if episodes and all(e is not None for e in episodes):
            aggregated[feature] = _combined([e for e in episodes if e is not None])
    return aggregated
