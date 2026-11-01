"""Moving an Episode's meta/episodes row and frames to its place in the export."""

import pyarrow as pa

from winnow.export.tables import rebased

QUANTILES = ("q01", "q10", "q50", "q90", "q99")


def _stats(column: str, low: int, high: int) -> dict[str, list[float]]:
    middle = (low + high) / 2
    return {
        f"stats/{column}/min": [low], f"stats/{column}/max": [high],
        f"stats/{column}/mean": [middle], f"stats/{column}/std": [1.5],
        **{f"stats/{column}/{q}": [middle] for q in QUANTILES},
    }  # fmt: skip


def test_rebasing_shifts_every_index_stat_but_std_and_remaps_the_task():
    row = {
        "episode_index": 7, "length": 4, "dataset_from_index": 100, "dataset_to_index": 104,
        **_stats("episode_index", 7, 7), **_stats("index", 100, 103),
        **_stats("task_index", 5, 5),
    }  # fmt: skip
    frames = pa.table({"task_index": [0, 0, 0, 0]})  # pyright: ignore[reportUnknownMemberType]

    moved = rebased(row, 2, 10, {}, frames)

    assert (moved["stats/episode_index/min"], moved["stats/episode_index/max"]) == ([2], [2])
    assert (moved["stats/index/min"], moved["stats/index/max"]) == ([10], [13])
    for q in ("mean", *QUANTILES):
        assert moved[f"stats/episode_index/{q}"] == [2.0]
        assert moved[f"stats/index/{q}"] == [11.5]
    assert moved["stats/index/std"] == [1.5]
    assert (moved["stats/task_index/min"], moved["stats/task_index/max"]) == ([0], [0])
    assert moved["stats/task_index/mean"] == [0.0]
    assert moved["stats/task_index/std"] == [0.0]
    assert all(moved[f"stats/task_index/{q}"] == [0.0] for q in QUANTILES)
