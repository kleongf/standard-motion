"""Calibration through the API: s is tuned per Rubric version on the Dev set's interview and
review labels only, scoring uses it, and accepting a threshold suggestion freezes a new version,
which starts at s = 1."""

from collections.abc import Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import OPEN_GRIPPER_EPISODE
from tests.helpers import app_context, reference_label, wait_for_job
from winnow.calibration import service as calibration_service
from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.models import Criterion
from winnow.evaluation import service as evaluation_service
from winnow.rubric.models import DraftPhrase, Rubric, RubricDraft
from winnow.rubric.seed import FIRST_TRY, NO_PAUSES, SEEDED
from winnow.triage.models import Label
from winnow.triage.scoring import score

# Path efficiency on the fixture Episodes: 0.387, 0.35, 0.338 in the Dev set; 0.613 in the Test
# set. Against ≥ 0.5 every one is crisp, with the ratio's 0.05 noise floor, at any s up to 2.
DEV = ["droid_100:0", "droid_100:1", f"droid_100:{OPEN_GRIPPER_EPISODE}"]
TEST = "droid_100:2"
PATH = Criterion(
    id="path-efficiency",
    phrase=NO_PAUSES,
    primitive="path_efficiency",
    comparator=">=",
    threshold=0.5,
    unit="ratio",
    assumptions=["A direct path covers at least half its length in a straight line."],
)
RUBRIC = SEEDED.model_copy(
    update={"criteria": [c for c in SEEDED.criteria if c.id != "longest-pause"] + [PATH]}
)


@pytest.fixture
def anchored(api: TestClient) -> TestClient:
    """Rubric v2 (the seed with a path-efficiency Criterion) over a Dev set of three Episodes."""
    indices = [0, 1, 2, OPEN_GRIPPER_EPISODE]
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": indices})
    wait_for_job(api, job.json()["job_id"])
    for episode_id in [*DEV, TEST]:
        reference_label(api, episode_id)  # reveals its outputs
    assert api.post("/api/sets/dev/episodes", json={"episode_ids": DEV}).status_code == 200
    assert api.post("/api/sets/test/episodes", json={"episode_ids": [TEST]}).status_code == 200
    assert app_context(api).rubrics.add(RUBRIC).version == 2
    return api


def label(
    api: TestClient, episode_id: str, value: str, source: str = "review", phrase: str = NO_PAUSES
) -> None:
    saved = api.post(
        f"/api/episodes/{episode_id}/labels",
        json={"phrase": phrase, "value": value, "source": source},
    )
    assert saved.status_code == 201, saved.text


def contradict_the_path(api: TestClient) -> None:
    """0.387 and 0.35 labelled fine though they fail; 0.338, as an interview answer, not fine."""
    label(api, DEV[0], "pass")
    label(api, DEV[1], "pass")
    label(api, DEV[2], "fail", source="interview")


def calibration(api: TestClient) -> Any:
    return api.get("/api/calibration").json()


def run(api: TestClient) -> Any:
    ran = api.post("/api/calibration/run")
    assert ran.status_code == 200, ran.text
    return ran.json()


def path_margin(api: TestClient, episode_id: str) -> float:
    triage = api.get(f"/api/episodes/{episode_id}/triage").json()
    return next(r["margin"] for r in triage["criteria"] if r["criterion_id"] == PATH.id)


def test_an_uncalibrated_version_is_scored_with_s_1(anchored: TestClient):
    found = calibration(anchored)

    assert (found["rubric_version"], found["s"], found["record"]) == (2, 1.0, None)
    assert (found["labelled"], found["suggestions"]) == (0, [])
    assert found["grid"] == [2.0, 1.5, 1.0, 0.75, 0.5]
    assert (found["max_error_rate"], found["confidence"]) == (0.2, 0.9)
    assert path_margin(anchored, DEV[0]) == 0.05


def test_calibrating_with_no_labels_is_refused(anchored: TestClient):
    refused = anchored.post("/api/calibration/run")

    assert refused.status_code == 409
    assert "label" in refused.json()["detail"]
    assert calibration(anchored)["record"] is None


def test_calibration_tunes_s_on_the_dev_labels_and_scoring_uses_it(anchored: TestClient):
    contradict_the_path(anchored)

    ran = run(anchored)

    # 2 of 3 wrong at every s: no s meets the bound, so s stays at the widest.
    record = ran["record"]
    assert (record["rubric_version"], record["s"], record["n_labels"]) == (2, 2.0, 3)
    assert (record["errors"], record["bound_met"], record["unstable"]) == (2, False, False)
    assert ran["s"] == 2.0 and calibration(anchored) == ran
    # Scoring and the version's anchor-pool preview both widen the margin: 0.05 * 2.
    assert path_margin(anchored, DEV[0]) == 0.1
    preview = anchored.get("/api/rubric/versions/2/preview").json()
    assert next(c for c in preview["criteria"] if c["criterion_id"] == PATH.id)["margin"] == 0.1


def test_test_set_and_audit_labels_are_never_read(anchored: TestClient):
    contradict_the_path(anchored)
    label(anchored, TEST, "fail")  # 0.613 passes: it would be a third error
    label(anchored, DEV[0], "fail", source="audit", phrase=FIRST_TRY)

    record = run(anchored)["record"]

    assert (record["n_labels"], record["errors"]) == (3, 2)


def test_two_contradicting_labels_suggest_a_threshold(anchored: TestClient):
    contradict_the_path(anchored)

    [suggestion] = calibration(anchored)["suggestions"]

    # Midway between the closest fine value (0.35) and not-fine one (0.338).
    assert suggestion["criterion_id"] == PATH.id
    assert (suggestion["suggested_threshold"], suggestion["suggested_margin"]) == (0.344, 0.012)
    assert (suggestion["contradicting"], suggestion["labelled"]) == (2, 3)


def accept(api: TestClient, criterion_id: str = PATH.id) -> Any:
    return api.post(f"/api/calibration/suggestions/{criterion_id}/accept")


def test_accepting_a_suggestion_freezes_a_new_version_which_starts_at_s_1(anchored: TestClient):
    contradict_the_path(anchored)
    run(anchored)

    accepted = accept(anchored)

    assert accepted.status_code == 201, accepted.text
    reply = accepted.json()
    version = reply["version"]
    path = next(c for c in version["rubric"]["criteria"] if c["id"] == PATH.id)
    assert version["version"] == 3
    assert (path["threshold"], path["margin"], path["assumptions"]) == (0.344, 0.012, [])
    assert [c for c in version["rubric"]["criteria"] if c["id"] != PATH.id] == [
        c.model_dump(mode="json") for c in RUBRIC.criteria if c.id != PATH.id
    ]
    assert reply["draft_updated"] is False
    assert reply["draft_note"] == "There's no Rubric draft to update."
    found = calibration(anchored)
    assert (found["rubric_version"], found["s"], found["record"]) == (3, 1.0, None)
    # The suggested margin is under the noise floor, so the effective margin is 0.05 again.
    assert path_margin(anchored, DEV[0]) == 0.05


def save_draft(api: TestClient, criteria: list[Criterion]) -> None:
    phrases = [
        DraftPhrase(
            text=p,
            start=(start := RUBRIC.description.index(p)),
            end=start + len(p),
            restatement=p,
            status="checked",
        )
        for p in RUBRIC.phrases
    ]
    app_context(api).drafts.save(
        RubricDraft(
            description=RUBRIC.description,
            phrases=phrases,
            settings=RUBRIC.settings,
            criteria=criteria,
            compiled_at="2026-10-30T00:00:00+00:00",
        )
    )


def draft_path(api: TestClient) -> Any:
    return next(c for c in api.get("/api/rubric/draft").json()["criteria"] if c["id"] == PATH.id)


def test_accepting_carries_the_new_threshold_into_the_draft(anchored: TestClient):
    contradict_the_path(anchored)
    save_draft(anchored, RUBRIC.criteria)

    reply = accept(anchored).json()

    assert reply["draft_updated"] is True
    assert reply["draft_note"] == "The draft's Criterion path-efficiency moved too."
    assert (draft_path(anchored)["threshold"], draft_path(anchored)["margin"]) == (0.344, 0.012)


def test_a_draft_criterion_changed_since_is_left_alone(anchored: TestClient):
    contradict_the_path(anchored)
    turned = PATH.model_copy(update={"comparator": "<="})
    save_draft(anchored, [c for c in RUBRIC.criteria if c.id != PATH.id] + [turned])

    accepted = accept(anchored)

    assert accepted.status_code == 201
    assert accepted.json()["draft_updated"] is False
    assert accepted.json()["draft_note"] == (
        "The draft's Criterion path-efficiency now compares differently "
        "(comparator, primitive or unit changed), so it was left as it is."
    )
    assert (draft_path(anchored)["comparator"], draft_path(anchored)["threshold"]) == ("<=", 0.5)


def test_a_failed_draft_write_freezes_no_version(
    anchored: TestClient, monkeypatch: pytest.MonkeyPatch
):
    contradict_the_path(anchored)
    save_draft(anchored, RUBRIC.criteria)

    def broken(_: RubricDraft) -> RubricDraft:
        raise RuntimeError("disk full")

    monkeypatch.setattr(app_context(anchored).drafts, "save", broken)
    with pytest.raises(RuntimeError):
        accept(anchored)

    assert len(anchored.get("/api/rubric/versions").json()) == 2
    assert draft_path(anchored)["threshold"] == 0.5


def test_accepting_what_labels_dont_suggest_is_refused(anchored: TestClient):
    contradict_the_path(anchored)

    refused = accept(anchored, "grasp-attempts")

    assert refused.status_code == 404
    assert len(anchored.get("/api/rubric/versions").json()) == 2


def test_an_evaluation_scores_the_version_with_its_s(
    anchored: TestClient, monkeypatch: pytest.MonkeyPatch
):
    contradict_the_path(anchored)
    run(anchored)
    seen: list[float] = []

    def spy(rubric: Rubric, facts: EpisodeFacts, labels: Sequence[Label] = (), s: float = 1.0):
        seen.append(s)
        return score(rubric, facts, labels, s)

    monkeypatch.setattr(evaluation_service, "score", spy)
    report = anchored.post("/api/evaluation/runs", json={"set_name": "dev"})

    assert report.status_code == 200, report.text
    assert seen and set(seen) == {2.0}


def test_calibrating_and_accepting_queue_spark_reasons(
    anchored: TestClient, monkeypatch: pytest.MonkeyPatch
):
    # Either can change Criterion results, and with them the Reasons Spark wrote.
    queued: list[int] = []

    def spy(ctx: object) -> None:
        queued.append(app_context(anchored).rubrics.latest().version)

    monkeypatch.setattr(calibration_service, "queue_reasons", spy)
    contradict_the_path(anchored)

    run(anchored)
    assert queued == [2]
    assert accept(anchored).status_code == 201
    assert queued == [2, 3]
