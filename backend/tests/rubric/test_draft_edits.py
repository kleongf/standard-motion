"""Direct edits on the Rubric draft, the anchor-pool preview they re-sort, and Run."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import reference_label, wait_for_job
from tests.rubric.scripted import ScriptedCompile, criterion, phrase
from winnow.app import create_app
from winnow.core.settings import Settings

DESCRIPTION = "Tidy pick: one grasp only, and no long pauses."
ONE_GRASP = "one grasp only"
NO_PAUSES = "no long pauses"
# Fixture Episode i grasps once unless i % 3 == 2, which fails two grasp attempts first.
DEV = ["droid_100:0", "droid_100:1", "droid_100:2"]
TEST = ["droid_100:4"]  # its gripper never closes


@pytest.fixture
def spark() -> ScriptedCompile:
    return ScriptedCompile(answers=[])


@pytest.fixture
def labelled() -> list[str]:
    """The Episodes with a Reference label: only their outputs may show."""
    return DEV + TEST


@pytest.fixture
def api(settings: Settings, spark: ScriptedCompile, labelled: list[str]) -> Iterator[TestClient]:
    with TestClient(create_app(settings, transport=spark)) as client:
        job = client.post(
            "/api/episodes/ingest", json={"source": "droid_100", "indices": [0, 1, 2, 4]}
        )
        wait_for_job(client, job.json()["job_id"])
        client.post("/api/sets/dev/episodes", json={"episode_ids": DEV})
        client.post("/api/sets/test/episodes", json={"episode_ids": TEST})
        for episode_id in labelled:
            reference_label(client, episode_id)
        yield client


@pytest.fixture
def drafted(api: TestClient, spark: ScriptedCompile) -> TestClient:
    pauses = criterion(
        "longest_still_s",
        "<",
        2.0,
        params={"speed_below_m_s": 0.01},
        assumptions=["A long pause is 2 s or more under 1 cm/s."],
    )
    spark.answers.append(
        {
            "phrases": [
                phrase("Tidy pick", "context", reason="Names the task."),
                phrase(ONE_GRASP, criteria=[criterion("grasp_attempts", "<=", 1)]),
                phrase(NO_PAUSES, criteria=[pauses]),
            ]
        }
    )
    response = api.post("/api/rubric/draft/compile", json={"description": DESCRIPTION})
    assert response.status_code == 200, response.text
    return api


def criterion_id(api: TestClient, primitive: str) -> str:
    draft = api.get("/api/rubric/draft").json()
    return next(c["id"] for c in draft["criteria"] if c["primitive"] == primitive)


def preview(api: TestClient, edit: dict[str, Any] | None = None) -> Any:
    response = api.post("/api/rubric/draft/preview", json=edit or {})
    assert response.status_code == 200, response.text
    return response.json()


def counts(preview: Any, criterion_id: str) -> tuple[int, int, int]:
    found = next(c for c in preview["criteria"] if c["criterion_id"] == criterion_id)
    return found["passing"], found["failing"], found["unsure"]


def test_a_dragged_threshold_re_sorts_the_anchor_pool_without_saving(drafted: TestClient):
    grasps = criterion_id(drafted, "grasp_attempts")
    assert counts(preview(drafted), grasps) == (2, 1, 0)

    dragged = preview(drafted, {"criteria": {grasps: {"threshold": 3}}})

    assert counts(dragged, grasps) == (3, 0, 0)
    saved = drafted.get("/api/rubric/draft").json()
    assert next(c for c in saved["criteria"] if c["id"] == grasps)["threshold"] == 1


@pytest.mark.parametrize("labelled", [[DEV[0], DEV[2], *TEST]])
def test_only_labelled_dev_set_episodes_count(drafted: TestClient):
    # The Test set Episode never grasps and the unlabelled one would pass: neither shows.
    pool = drafted.get("/api/anchor-pool").json()
    assert (len(pool["episode_ids"]), pool["hidden_test_episodes"]) == (3, 1)
    assert pool["awaiting_reference_label"] == 1

    shown = preview(drafted)

    grasps = criterion_id(drafted, "grasp_attempts")
    assert counts(shown, grasps) == (1, 1, 0)
    assert sorted(e["episode_id"] for e in shown["episodes"]) == [DEV[0], DEV[2]]
    for found in shown["criteria"]:
        assert sorted(v["episode_id"] for v in found["values"]) == [DEV[0], DEV[2]]


def patch(api: TestClient, edit: dict[str, Any]) -> Any:
    response = api.patch("/api/rubric/draft", json=edit)
    assert response.status_code == 200, response.text
    return response.json()


def test_a_soft_criterion_shows_its_counts_but_never_rejects(drafted: TestClient):
    grasps = criterion_id(drafted, "grasp_attempts")
    assert preview(drafted)["reject"] == 1

    draft = patch(drafted, {"criteria": {grasps: {"hard": False}}})

    assert next(c for c in draft["criteria"] if c["id"] == grasps)["hard"] is False
    softened = preview(drafted)
    assert (softened["keep"], softened["reject"]) == (3, 0)
    assert counts(softened, grasps) == (2, 1, 0)


def test_a_criterion_switched_off_is_shown_but_not_scored(drafted: TestClient):
    pauses = criterion_id(drafted, "longest_still_s")
    grasps = criterion_id(drafted, "grasp_attempts")
    assert drafted.get("/api/rubric/draft").json()["assumptions_unconfirmed"] == 3

    draft = patch(drafted, {"criteria": {pauses: {"enabled": False}, grasps: {"enabled": False}}})

    assert sorted(draft["disabled"]) == sorted([pauses, grasps])
    assert draft["assumptions_unconfirmed"] == 2  # the pause's guess no longer runs
    off = preview(drafted)
    assert (off["keep"], off["reject"]) == (3, 0)
    assert counts(off, grasps) == (2, 1, 0)  # its histogram still shows
    back_on = patch(drafted, {"criteria": {grasps: {"enabled": True}}})
    assert back_on["disabled"] == [pauses]


def test_setting_a_rubric_setting_confirms_it_and_re_sorts(drafted: TestClient):
    grasps = criterion_id(drafted, "grasp_attempts")

    # The fixture's grasps close the gripper to under 0.95, so none is a grasp at that level.
    stricter = preview(drafted, {"gripper_closed_level": 0.95})
    draft = patch(drafted, {"gripper_closed_level": 0.95, "grasp_rise_m": 0.03})

    assert counts(stricter, grasps) != (2, 1, 0)
    closed, rise = draft["settings"]["gripper_closed_level"], draft["settings"]["grasp_rise_m"]
    assert (closed["value"], closed["assumption"]) == (0.95, None)
    assert (rise["value"], rise["assumption"]) == (0.03, None)
    assert closed["margin"] == 0.1  # kept
    assert draft["assumptions_unconfirmed"] == 1


def test_editing_with_no_draft_is_refused(api: TestClient):
    assert api.patch("/api/rubric/draft", json={}).status_code == 404
    assert api.post("/api/rubric/draft/preview", json={}).status_code == 404
    assert api.post("/api/rubric/draft/run").status_code == 404


def test_an_unknown_criterion_is_refused(drafted: TestClient):
    response = drafted.patch("/api/rubric/draft", json={"criteria": {"nope": {"hard": False}}})

    assert response.status_code == 422
    assert "nope" in response.json()["detail"]


def test_run_freezes_the_draft_into_a_new_version_that_scores_every_episode(
    drafted: TestClient,
):
    pauses = criterion_id(drafted, "longest_still_s")
    grasps = criterion_id(drafted, "grasp_attempts")
    patch(drafted, {"criteria": {pauses: {"enabled": False}, grasps: {"threshold": 3}}})

    response = drafted.post("/api/rubric/draft/run")

    assert response.status_code == 201, response.text
    run = response.json()
    assert (run["version"], run["origin"]) == (2, "run")  # after the seeded version 1
    assert run["rubric"]["description"] == DESCRIPTION
    assert run["rubric"]["phrases"] == ["Tidy pick", ONE_GRASP, NO_PAUSES]
    assert [(c["id"], c["threshold"]) for c in run["rubric"]["criteria"]] == [(grasps, 3)]
    assert drafted.get("/api/rubric").json() == run
    versions = drafted.get("/api/rubric/versions").json()
    assert [(v["version"], v["origin"]) for v in versions] == [(2, "run"), (1, "seed")]
    # Results name their version: Episode 2's three attempts now pass, and Episode 4, which
    # never grasps, still fails.
    triage = drafted.get("/api/triage").json()
    assert triage["rubric_version"] == 2
    assert drafted.get("/api/episodes/droid_100:2/triage").json()["rubric_version"] == 2
    decisions = {r["episode_id"]: r["decision"] for r in triage["rows"]}
    assert decisions == {**dict.fromkeys(DEV, "keep"), TEST[0]: "reject"}


def test_a_run_version_never_changes_as_the_draft_does(drafted: TestClient):
    grasps = criterion_id(drafted, "grasp_attempts")
    run = drafted.post("/api/rubric/draft/run").json()

    patch(drafted, {"criteria": {grasps: {"threshold": 3}}})
    again = drafted.post("/api/rubric/draft/run").json()

    assert again["version"] == run["version"] + 1
    versions = {v["version"]: v for v in drafted.get("/api/rubric/versions").json()}
    assert versions[run["version"]] == run
    frozen = drafted.get(f"/api/rubric/versions/{run['version']}/preview").json()
    assert frozen["rubric_version"] == run["version"]
    assert counts(frozen, grasps) == (2, 1, 0)  # its threshold is still 1
    assert counts(preview(drafted), grasps) == (3, 0, 0)
    assert drafted.get("/api/rubric/versions/99/preview").status_code == 404
