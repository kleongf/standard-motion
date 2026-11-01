"""Every paid call reserves its estimate against the budget before it is sent, and settles its
actual cost when it returns, so calls in flight together can't overspend."""

import json
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


class BudgetExceededError(RuntimeError):
    pass


@dataclass(frozen=True)
class CostEntry:
    model: str
    purpose: str
    usd: float
    latency_s: float
    detail: dict[str, int | float | str]


class CostLog:
    def __init__(self, path: Path, budget_usd: float) -> None:
        self.path = path
        self.budget_usd = budget_usd
        self._reserved_usd = 0.0  # estimates of calls in flight in this process

    def spent_usd(self) -> float:
        return sum(entry.usd for entry in self.entries())

    def entries(self) -> list[CostEntry]:
        """Every logged call, oldest first; a cache hit is logged at $0."""
        if not self.path.exists():
            return []
        rows = [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]
        return [
            CostEntry(
                str(row["model"]),
                str(row["purpose"]),
                float(row["usd"]),
                float(row.get("latency_s", 0.0)),
                dict(row.get("detail", {})),
            )
            for row in rows
        ]

    def ensure_affordable(self, estimate_usd: float) -> None:
        committed = self.spent_usd() + self._reserved_usd
        if committed + estimate_usd > self.budget_usd:
            raise BudgetExceededError(
                f"Call would cost up to ${estimate_usd:.4f}; ${committed:.4f} of the "
                f"${self.budget_usd:.2f} budget is already spent or reserved."
            )

    @contextmanager
    def reserve(self, estimate_usd: float) -> Generator[None]:
        """Hold `estimate_usd` of the budget until the block exits; record the real cost inside."""
        self.ensure_affordable(estimate_usd)
        self._reserved_usd += estimate_usd
        try:
            yield
        finally:
            self._reserved_usd -= estimate_usd

    def record(self, entry: CostEntry) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        row = {"at": datetime.now(UTC).isoformat(), **asdict(entry)}
        with self.path.open("a") as f:
            f.write(json.dumps(row) + "\n")
