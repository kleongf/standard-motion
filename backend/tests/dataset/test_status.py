from fastapi.testclient import TestClient

from standard_motion.core.settings import Settings
from standard_motion.meta.costs import CostEntry, CostLog
from tests.helpers import wait_for_job


def test_status_counts_ingested_episodes_per_source_and_meta_spend(
    api: TestClient, settings: Settings
):
    CostLog(settings.data_dir / "meta_costs.jsonl", 5.0).record(
        CostEntry("sam-3.1", "test", 0.25, 1.0, {})
    )
    before = api.get("/api/dataset").json()
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [0, 1]})
    wait_for_job(api, job.json()["job_id"])

    after = api.get("/api/dataset").json()

    assert before["episodes"] == 0
    assert after["episodes"] == 2
    assert after["sources"] == [{"name": "droid_100", "episodes": 2}]
    assert after["cost_usd"] == 0.25
