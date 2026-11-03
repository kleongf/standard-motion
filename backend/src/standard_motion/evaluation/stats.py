"""Honest statistics from few labels: a count plus an interval, never "±"."""

from collections.abc import Callable
from math import exp, lgamma, log, log1p, sqrt

from pydantic import BaseModel


class Proportion(BaseModel):
    """`count` of `of`, with its 95% Wilson interval; no interval when `of` is 0."""

    count: int
    of: int
    low: float | None
    high: float | None


Z_95 = 1.959964  # two-sided 95%


def wilson(count: int, of: int, z: float = Z_95) -> Proportion:
    """The Wilson score interval, which stays inside [0, 1] and behaves at 0 and n."""
    if of == 0:
        return Proportion(count=0, of=0, low=None, high=None)
    p = count / of
    z2 = z * z
    denominator = 1 + z2 / of
    centre = (p + z2 / (2 * of)) / denominator
    half = z * sqrt(p * (1 - p) / of + z2 / (4 * of * of)) / denominator
    return Proportion(count=count, of=of, low=max(0.0, centre - half), high=min(1.0, centre + half))


def _binomial_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p). The terms are summed in log space, because C(n, i) alone
    overflows a float once n passes about 1030."""
    if k >= n:
        return 1.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0
    log_p, log_q = log(p), log1p(-p)
    log_c = lgamma(n + 1)
    logs = [
        log_c - lgamma(i + 1) - lgamma(n - i + 1) + i * log_p + (n - i) * log_q
        for i in range(k + 1)
    ]
    top = max(logs)
    return min(1.0, exp(top) * sum(exp(term - top) for term in logs))


def _bisect(falling: Callable[[float], float], target: float, low: float, high: float) -> float:
    """The p in [low, high] where `falling`, which falls as p rises, crosses `target`."""
    for _ in range(100):
        mid = (low + high) / 2
        if falling(mid) > target:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def _check(k: int, n: int, conf: float) -> None:
    if not 0 <= k <= n:
        raise ValueError(f"{k} of {n} isn't a count")
    if not 0 < conf < 1:
        raise ValueError(f"A confidence of {conf} isn't between 0 and 1")


def clopper_pearson_upper(k: int, n: int, conf: float) -> float:
    """The exact one-sided upper bound on a rate seen `k` times in `n`, at `conf` (e.g. 0.9):
    the rate at which `k` or fewer would turn up only 1 - `conf` of the time."""
    _check(k, n, conf)
    if k == n:
        return 1.0
    return _bisect(lambda p: _binomial_cdf(k, n, p), 1 - conf, 0.0, 1.0)


def clopper_pearson_lower(k: int, n: int, conf: float) -> float:
    """The exact one-sided lower bound on a rate seen `k` times in `n`, at `conf`. When every one
    is seen (k = n) it is (1 - conf)^(1/n): 15 of 15 at 90% gives 0.86."""
    _check(k, n, conf)
    if k == 0:
        return 0.0
    # P(X >= k) = 1 - P(X <= k - 1) rises with p; the bound is where it reaches 1 - conf.
    return _bisect(lambda p: _binomial_cdf(k - 1, n, p), conf, 0.0, 1.0)
