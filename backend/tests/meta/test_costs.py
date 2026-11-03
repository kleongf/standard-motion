from pathlib import Path

import pytest

from standard_motion.meta.costs import BudgetExceededError, CostEntry, CostLog
from standard_motion.meta.pricing import SPARK_CONTRIBUTOR, sam_cost, spark_cost


def entry(usd: float) -> CostEntry:
    return CostEntry(model="sam-3.1", purpose="test", usd=usd, latency_s=1.0, detail={})


def test_spend_accumulates_across_records(tmp_path: Path):
    log = CostLog(tmp_path / "costs.jsonl", budget_usd=5.0)
    log.record(entry(1.25))
    log.record(entry(0.75))
    assert log.spent_usd() == pytest.approx(2.0)


def test_call_that_would_cross_the_budget_is_refused(tmp_path: Path):
    log = CostLog(tmp_path / "costs.jsonl", budget_usd=5.0)
    log.record(entry(4.90))
    log.ensure_affordable(0.10)
    with pytest.raises(BudgetExceededError):
        log.ensure_affordable(0.11)


def test_sam_bills_at_least_fifty_frames():
    assert sam_cost(10) == pytest.approx(0.01)
    assert sam_cost(331) == pytest.approx(0.0662)


def test_spark_contributor_pricing():
    assert spark_cost(SPARK_CONTRIBUTOR, 1_000_000, 1_000_000) == pytest.approx(0.30)
