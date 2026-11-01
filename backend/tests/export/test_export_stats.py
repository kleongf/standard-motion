"""meta/stats.json combines the kept Episodes' own stats as LeRobot's aggregate_stats does."""

import numpy as np
import pyarrow as pa
import pytest

from winnow.export.stats import aggregate_stats, episode_stats


def test_an_episodes_stats_cover_its_numeric_and_boolean_columns_per_dimension():
    frames = pa.table(  # pyright: ignore[reportUnknownMemberType]
        {
            "state": [[0.0, 10.0], [1.0, 20.0], [2.0, 30.0], [3.0, 40.0]],
            "index": [4, 5, 6, 7],
            "done": [False, False, False, True],
            "language_instruction": ["Put the marker in the pot"] * 4,
        }
    )

    stats = episode_stats(frames)

    assert stats["stats/state/min"] == [0.0, 10.0]
    assert stats["stats/state/max"] == [3.0, 40.0]
    assert stats["stats/state/mean"] == [1.5, 25.0]
    assert stats["stats/state/std"] == pytest.approx([np.sqrt(1.25), np.sqrt(125.0)])
    assert stats["stats/state/count"] == [4]
    assert stats["stats/state/q50"] == [1.5, 25.0]
    assert (stats["stats/index/min"], stats["stats/index/max"]) == ([4], [7])
    assert (stats["stats/done/min"], stats["stats/done/max"]) == ([False], [True])
    assert stats["stats/done/mean"] == [0.25]
    assert not any(k.startswith("stats/language_instruction/") for k in stats)


def _row(feature: str, **stats: object) -> dict[str, object]:
    return {f"stats/{feature}/{name}": value for name, value in stats.items()}


def test_episodes_combine_into_a_weighted_mean_a_pooled_std_and_count_weighted_quantiles():
    first = _row("x", min=[0.0], max=[2.0], mean=[1.0], std=[1.0], count=[1], q50=[1.0])
    second = _row("x", min=[-1.0], max=[9.0], mean=[4.0], std=[2.0], count=[3], q50=[5.0])

    [(feature, stats)] = aggregate_stats([first, second]).items()

    assert feature == "x"
    assert (stats["min"], stats["max"], stats["count"]) == ([-1.0], [9.0], [4])
    assert stats["mean"] == [3.25]  # (1 * 1 + 4 * 3) / 4
    # The pooled variance: each Episode's variance plus its mean's distance from the whole's.
    variance = (1 * (1 + 2.25**2) + 3 * (4 + 0.75**2)) / 4
    assert stats["std"] == pytest.approx([np.sqrt(variance)])
    assert stats["q50"] == [4.0]  # LeRobot's approximation: (1 * 1 + 5 * 3) / 4


def test_image_stats_are_weighted_per_channel():
    image = {"min": [[[0.0]], [[0.0]]], "max": [[[1.0]], [[1.0]]], "std": [[[0.0]], [[0.0]]]}
    first = _row("camera", **image, mean=[[[0.2]], [[0.4]]], count=[100])
    second = _row("camera", **image, mean=[[[0.6]], [[0.8]]], count=[300])

    stats = aggregate_stats([first, second])["camera"]

    assert np.allclose(stats["mean"], [[[0.5]], [[0.7]]])
    assert stats["count"] == [400]


def test_a_feature_missing_its_mean_std_or_count_anywhere_is_left_out():
    first = _row("x", min=[0.0], max=[1.0], mean=[0.5], std=[0.5], count=[2])
    second = _row("x", max=[1.0])

    assert aggregate_stats([first, second]) == {}
