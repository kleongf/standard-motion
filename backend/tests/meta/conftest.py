"""Fixtures for Meta client tests: a fake transport, a fake clock, and a client factory."""

from pathlib import Path

import pytest

from tests.meta.fakes import FakeTime, FakeTransport, MakeClient
from winnow.core.db import open_db
from winnow.meta.client import MetaClient
from winnow.meta.costs import CostLog
from winnow.meta.limits import Limit
from winnow.meta.pricing import SAM, SPARK_CONTRIBUTOR, VOICE_TRANSCRIBE

UNLIMITED = {model: Limit(in_flight=100) for model in (SAM, SPARK_CONTRIBUTOR, VOICE_TRANSCRIBE)}


@pytest.fixture
def transport() -> FakeTransport:
    return FakeTransport()


@pytest.fixture
def fake_time() -> FakeTime:
    return FakeTime()


@pytest.fixture
def make_client(tmp_path: Path, transport: FakeTransport, fake_time: FakeTime) -> MakeClient:
    db = open_db(tmp_path / "winnow.db")

    def make(budget_usd: float = 5.0, limits: dict[str, Limit] | None = None) -> MetaClient:
        return MetaClient(
            transport,
            db,
            CostLog(tmp_path / "meta_costs.jsonl", budget_usd),
            limits=UNLIMITED if limits is None else limits,
            clock=fake_time.clock,
            sleep=fake_time.sleep,
        )

    return make
