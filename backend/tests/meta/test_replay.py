import asyncio
from pathlib import Path

import pytest

from standard_motion.core.db import open_db
from standard_motion.meta.client import MetaClient
from standard_motion.meta.costs import CostLog
from standard_motion.meta.models import SparkRequest, Text
from standard_motion.meta.pricing import SPARK_CONTRIBUTOR
from standard_motion.meta.replay import (
    OfflineTransport,
    UnrecordedCallError,
    export_recordings,
    load_recordings,
)
from tests.meta.conftest import UNLIMITED
from tests.meta.fakes import MakeClient


def ask(question: str) -> SparkRequest:
    return SparkRequest(SPARK_CONTRIBUTOR, (Text(question),), {"type": "object"}, "test")


def offline_client(tmp_path: Path, recordings: Path) -> MetaClient:
    db = open_db(tmp_path / "replay.db")
    load_recordings(db, recordings)
    costs = CostLog(tmp_path / "replay_costs.jsonl", budget_usd=5.0)
    return MetaClient(OfflineTransport(), db, costs, limits=UNLIMITED)


def test_recorded_responses_replay_and_unrecorded_requests_fail_loudly(
    make_client: MakeClient, tmp_path: Path
):
    recorded = asyncio.run(make_client().spark(ask("Did it spill?")))
    recordings = tmp_path / "recordings.jsonl"
    export_recordings(open_db(tmp_path / "standard-motion.db"), recordings)

    client = offline_client(tmp_path, recordings)
    replayed = asyncio.run(client.spark(ask("Did it spill?")))

    assert replayed.cached and replayed.text == recorded.text
    with pytest.raises(UnrecordedCallError, match="Is it upright"):
        asyncio.run(client.spark(ask("Is it upright?")))
