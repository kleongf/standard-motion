"""Cost per 1,000 Episodes from the cost log, and review minutes from the label-mode timer."""

import pytest

from tests.evaluation.labelled import case
from winnow.evaluation.cost import meta_cost, review_time, step_and_episode
from winnow.meta.costs import CostEntry

TEST_SET = [f"droid_100:{i}" for i in range(100)]


def spent(purpose: str, usd: float, model: str = "sam-3.1") -> CostEntry:
    return CostEntry(model, purpose, usd, 1.0, {})


def hit(purpose: str) -> CostEntry:
    return CostEntry("sam-3.1", purpose, 0.0, 0.0, {"cache": "hit", "original_usd": 0.01})


LOG = [
    spent("track_wrist:droid_100:0", 0.01),
    spent("track_wrist:droid_100:1", 0.01),
    hit("track_wrist:droid_100:1"),  # asked again: cached, so free
    spent("track_exterior:droid_100:0", 0.02),
    spent("target_box:droid_100:0", 0.01),
    spent("visual:droid_100:0:placed-on-target", 0.0005, "muse-spark-1.3-contributor"),
    spent("visual:droid_100:1:placed-on-target", 0.0005, "muse-spark-1.3-contributor"),
    spent("baseline:droid_100:0", 0.003, "muse-spark-1.3-contributor"),
    spent("track_wrist:droid_1.0.1:9", 0.03),  # not in the set
    spent("compile", 0.002, "muse-spark-1.3-contributor"),
    spent("feasibility:A:ep42:gripper", 0.0662),  # names no Episode
]


def test_a_purpose_names_its_step_and_episode():
    assert step_and_episode("track_wrist:droid_100:3") == ("track_wrist", "droid_100:3")
    assert step_and_episode("visual:droid_1.0.1:9:placed-on-target") == ("visual", "droid_1.0.1:9")
    assert step_and_episode("compile") is None


def test_cost_per_1000_episodes_is_ten_times_a_test_set_of_100():
    cost = meta_cost(LOG, TEST_SET)

    assert cost.episodes == 100
    assert cost.winnow_usd == pytest.approx(0.051)
    assert cost.winnow_per_1000_usd == pytest.approx(0.51)  # x10
    assert cost.spark_alone_usd == pytest.approx(0.003)
    assert cost.spark_alone_per_1000_usd == pytest.approx(0.03)
    assert cost.compile_usd == pytest.approx(0.002)


def test_each_step_counts_paid_calls_and_episodes_but_not_cache_hits():
    steps = {s.step: (s.system, s.calls, s.episodes, s.usd) for s in meta_cost(LOG, TEST_SET).steps}

    assert list(steps) == ["track_wrist", "track_exterior", "target_box", "visual", "baseline"]
    assert steps["track_wrist"] == ("winnow", 2, 2, pytest.approx(0.02))
    assert steps["visual"] == ("winnow", 2, 2, pytest.approx(0.001))
    assert steps["baseline"] == ("spark_alone", 1, 1, pytest.approx(0.003))


def test_a_smaller_set_extrapolates_per_episode():
    cost = meta_cost(LOG, ["droid_100:0", "droid_100:1"])

    assert cost.winnow_per_1000_usd == pytest.approx(0.051 / 2 * 1000)


def test_an_empty_set_has_no_extrapolation():
    cost = meta_cost(LOG, [])

    assert (cost.winnow_usd, cost.winnow_per_1000_usd, cost.steps) == (0.0, None, [])


def test_minutes_saved_are_the_timers_minutes_per_episode_times_episodes_decided():
    cases = [
        case(0, None, "keep", elapsed_s=60),
        case(1, None, "reject", elapsed_s=120),
        case(2, None, "needs_review", elapsed_s=90),
    ]

    time = review_time(cases)

    assert (time.timed, time.decided) == (3, 2)
    assert time.minutes_per_episode == pytest.approx(1.5)
    assert time.minutes_saved == pytest.approx(3.0)
    assert (time.needs_review.count, time.needs_review.of) == (1, 3)
    # The human cost per Episode left: a third of Episodes reviewed, at 1.5 min each.
    assert time.needs_review_minutes_per_episode == pytest.approx(0.5)


def test_nothing_labelled_saves_nothing_measurable():
    time = review_time([])

    assert (time.minutes_per_episode, time.minutes_saved) == (None, None)
    assert time.needs_review_minutes_per_episode is None
