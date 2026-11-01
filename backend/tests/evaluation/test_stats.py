"""Intervals from few labels, checked against known values."""

from math import comb

import pytest

from winnow.evaluation.stats import clopper_pearson_lower, clopper_pearson_upper, wilson


def test_wilson_on_14_of_15_is_0_70_to_0_99():
    p = wilson(14, 15)

    assert (p.count, p.of) == (14, 15)
    assert (round(p.low or 0, 2), round(p.high or 0, 2)) == (0.70, 0.99)


def test_the_one_sided_lower_bound_when_every_one_is_good_is_the_nth_root_of_1_minus_conf():
    assert clopper_pearson_lower(15, 15, 0.90) == pytest.approx(0.1 ** (1 / 15), abs=1e-9)
    assert round(clopper_pearson_lower(15, 15, 0.90), 2) == 0.86


def test_the_one_sided_upper_bound_when_none_is_seen_mirrors_it():
    assert clopper_pearson_upper(0, 10, 0.90) == pytest.approx(1 - 0.1 ** (1 / 10), abs=1e-9)


def test_two_one_sided_bounds_at_97_5_percent_make_the_two_sided_95_percent_interval():
    # The exact (Clopper–Pearson) 95% interval for 2 of 20 is 0.0123–0.3170.
    assert clopper_pearson_lower(2, 20, 0.975) == pytest.approx(0.01235, abs=5e-5)
    assert clopper_pearson_upper(2, 20, 0.975) == pytest.approx(0.31698, abs=5e-5)


def test_the_bounds_stop_at_0_and_1():
    assert clopper_pearson_lower(0, 10, 0.90) == 0.0
    assert clopper_pearson_upper(10, 10, 0.90) == 1.0
    assert (clopper_pearson_lower(0, 0, 0.90), clopper_pearson_upper(0, 0, 0.90)) == (0.0, 1.0)


def test_an_impossible_count_is_refused():
    with pytest.raises(ValueError):
        clopper_pearson_upper(11, 10, 0.90)
    with pytest.raises(ValueError):
        clopper_pearson_lower(1, 2, 1.0)


def test_a_large_sample_does_not_overflow():
    # C(1100, i) alone is past a float's range; the bounds still sit near the normal approximation
    # 0.5 +- 1.2816 * sqrt(0.25 / 1100) = 0.4807 / 0.5193.
    upper = clopper_pearson_upper(550, 1100, 0.9)
    lower = clopper_pearson_lower(550, 1100, 0.9)

    assert upper == pytest.approx(0.5193, abs=2e-3)
    assert lower == pytest.approx(0.4807, abs=2e-3)
    assert lower == pytest.approx(1 - upper, abs=1e-6)  # symmetric at k = n / 2


def test_below_50_percent_confidence_the_bounds_cross_to_the_other_side_of_the_rate():
    # At 30% the upper bound is where P(X <= 5) = 0.7, below the observed 0.5; the lower bound
    # mirrors it above.
    upper = clopper_pearson_upper(5, 10, 0.3)
    lower = clopper_pearson_lower(5, 10, 0.3)

    assert upper < 0.5 < lower
    assert sum(comb(10, i) * upper**i * (1 - upper) ** (10 - i) for i in range(6)) == pytest.approx(
        0.7, abs=1e-9
    )
    assert lower == pytest.approx(1 - upper, abs=1e-9)
