"""Drawing the Audit sample and reading Keep precision from its marks, without the app."""

import pytest

from winnow.audit.models import AuditMark
from winnow.audit.service import KEEPS, REJECTS, draw, keep_precision


def ids(prefix: str, count: int) -> list[str]:
    return [f"{prefix}{i}" for i in range(count)]


def test_the_same_seed_draws_the_same_sample():
    keeps, rejects = ids("k", 40), ids("r", 20)

    assert draw(keeps, rejects, seed=3) == draw(keeps, rejects, seed=3)
    assert draw(keeps, rejects, seed=3) != draw(keeps, rejects, seed=4)


def test_it_draws_12_keeps_and_5_rejects_in_the_order_given():
    keeps, rejects = ids("k", 40), ids("r", 20)

    picks = draw(keeps, rejects, seed=3)

    kept = [p.episode_id for p in picks if p.kind == "keep"]
    rejected = [p.episode_id for p in picks if p.kind == "reject"]
    assert (len(kept), len(rejected)) == (KEEPS, REJECTS) == (12, 5)
    assert kept == sorted(kept, key=keeps.index) and rejected == sorted(rejected, key=rejects.index)
    assert [p.kind for p in picks] == ["keep"] * 12 + ["reject"] * 5


def test_a_small_pool_is_drawn_whole():
    picks = draw(["k0", "k1"], [], seed=3)

    assert [(p.episode_id, p.kind) for p in picks] == [("k0", "keep"), ("k1", "keep")]


def marks(good: int, bad: int = 0) -> list[AuditMark | None]:
    return ["good" if i < good else "bad" for i in range(good + bad)]


def test_14_of_15_good_is_wilson_0_70_to_0_99_with_no_one_sided_bound():
    precision = keep_precision(marks(14, 1))

    good = precision.good
    assert (good.count, good.of) == (14, 15)
    assert (round(good.low or 0, 2), round(good.high or 0, 2)) == (0.70, 0.99)
    assert precision.lower_bound is None


def test_15_of_15_good_is_at_least_0_86_at_90_percent():
    precision = keep_precision(marks(15))

    assert precision.lower_bound == pytest.approx(0.858, abs=1e-3)
    assert precision.lower_bound_confidence == 0.9


def test_unmarked_items_are_not_counted():
    precision = keep_precision(["good", None, None])

    assert (precision.good.count, precision.good.of) == (1, 1)
    assert keep_precision([None]).good.of == 0
    assert keep_precision([None]).lower_bound is None
