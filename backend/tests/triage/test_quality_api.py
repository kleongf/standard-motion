"""The Episodes table lists each Episode's quality within the run; soft Criteria rank Episodes
and never move a Triage decision."""

import pytest
from fastapi.testclient import TestClient

from tests.helpers import app_context, reference_label, wait_for_job
from winnow.rubric.models import Rubric

# Fixture Episodes release 1.8 cm (i % 3 == 0) and 4.4 cm (i % 6 == 1) above where they picked
# up, and the regrasp (i % 3 == 2) 6.5 cm.
LOW, HIGHER, HIGHEST = "droid_100:0", "droid_100:1", "droid_100:2"


@pytest.fixture
def ingested(api: TestClient) -> TestClient:
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [0, 1, 2]})
    wait_for_job(api, job.json()["job_id"])
    for id_ in (LOW, HIGHER, HIGHEST):
        reference_label(api, id_)
    return api


def rows(api: TestClient) -> dict[str, dict[str, object]]:
    return {r["episode_id"]: r for r in api.get("/api/triage").json()["rows"]}


def add_soft_release_height(api: TestClient) -> None:
    """The latest Rubric plus a soft copy of its release height: lower releases rank higher."""
    rubrics = app_context(api).rubrics
    rubric = rubrics.latest().rubric.model_copy(deep=True)
    height = next(c for c in rubric.criteria if c.id == "release-height")
    rubric.criteria.append(height.model_copy(update={"id": "soft-release-height", "hard": False}))
    rubrics.add(Rubric.model_validate(rubric.model_dump()))


def test_with_no_soft_criterion_no_episode_has_a_quality(ingested: TestClient):
    assert {id_: r["quality"] for id_, r in rows(ingested).items()} == {
        LOW: None,
        HIGHER: None,
        HIGHEST: None,
    }


def test_a_soft_criterion_ranks_episodes_by_quality_and_moves_no_decision(ingested: TestClient):
    before = {id_: r["decision"] for id_, r in rows(ingested).items()}

    add_soft_release_height(ingested)

    after = rows(ingested)
    assert {id_: r["decision"] for id_, r in after.items()} == before
    quality = {id_: r["quality"] for id_, r in after.items()}
    assert quality[HIGHER] == 0  # the median
    assert quality[LOW] > 0 > quality[HIGHEST]  # type: ignore[operator]
