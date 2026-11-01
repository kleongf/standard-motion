"""Spark's Reason replaces the template Reason only while it was written for the same inputs."""

import pytest
from fastapi.testclient import TestClient

from tests.helpers import app_context, reference_label, wait_for_job
from winnow.baseline.prompts import FROZEN
from winnow.criteria.models import TextSpan
from winnow.rubric.models import Rubric
from winnow.triage.models import Triage
from winnow.triage.spark_reason import reason_key

FIRST_TRY = FROZEN.phrases[0]
REGRASP = "droid_100:2"  # rejected: two failed grasp attempts before the grasp
WRITTEN = [
    TextSpan(text="Two grasps slipped before it held, the first at "),
    TextSpan(text="0.9 s", t=0.9333333333333333),
    TextSpan(text="."),
]


@pytest.fixture
def rejected(api: TestClient) -> TestClient:
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [2]})
    wait_for_job(api, job.json()["job_id"])
    reference_label(api, REGRASP)
    return api


def triage_of(api: TestClient) -> dict[str, object]:
    return api.get(f"/api/episodes/{REGRASP}/triage").json()


def store_spark_reason(api: TestClient) -> list[dict[str, object]]:
    """Spark's Reason, stored for the Episode's template triage as it stands; the template."""
    template = triage_of(api)
    ctx = app_context(api)
    version = ctx.rubrics.latest().version
    ctx.reasons.put(REGRASP, reason_key(version, Triage.model_validate(template)), WRITTEN)
    return template["reason"]  # type: ignore[return-value]


def test_the_template_reason_shows_until_spark_writes_one(rejected: TestClient):
    triage = triage_of(rejected)

    assert triage["reason_source"] == "template"
    assert str(triage["reason"][0]["text"]).startswith("Rejected:")  # type: ignore[index]


def test_spark_s_reason_replaces_the_template_for_the_same_inputs(rejected: TestClient):
    store_spark_reason(rejected)

    triage = triage_of(rejected)

    assert triage["reason_source"] == "spark"
    assert triage["reason"] == [s.model_dump() for s in WRITTEN]
    [row] = rejected.get("/api/triage").json()["rows"]
    assert row["reason"] == "Two grasps slipped before it held, the first at 0.9 s."


def test_a_label_falls_back_to_the_template(rejected: TestClient):
    store_spark_reason(rejected)

    label = {"phrase": FIRST_TRY, "value": "fail", "source": "review"}
    assert rejected.post(f"/api/episodes/{REGRASP}/labels", json=label).status_code == 201

    triage = triage_of(rejected)
    assert triage["decision"] == "reject"
    assert triage["reason_source"] == "template"


def test_a_threshold_change_falls_back_to_the_template(rejected: TestClient):
    template = store_spark_reason(rejected)
    rubrics = app_context(rejected).rubrics
    stricter = rubrics.latest().rubric.model_copy(deep=True)
    attempts = next(c for c in stricter.criteria if c.id == "grasp-attempts")
    attempts.threshold = 2  # still fails: 3 attempts

    rubrics.add(Rubric.model_validate(stricter.model_dump()))

    triage = triage_of(rejected)
    assert triage["decision"] == "reject"
    assert triage["reason_source"] == "template"
    assert triage["reason"] == template
