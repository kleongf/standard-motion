"""A threshold drag re-sorts the anchor pool with zero Meta calls, and a sentence edit with one
call about the edited Phrase, against the replay transport serving Spark's recorded compile of
the frozen Description and its recorded recompile."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tests.helpers import reference_label, wait_for_job
from tests.record_meta import EDITED, RECORDINGS
from tests.rubric.replay import CountingReplay
from winnow.app import create_app
from winnow.baseline.prompts import FROZEN
from winnow.core.settings import Settings
from winnow.meta.replay import ReplayTransport

ANCHOR = "droid_100:0"  # the robot data of e2e's Dev set, which compile was recorded against


@pytest.fixture
def transport() -> CountingReplay:
    return CountingReplay(ReplayTransport(RECORDINGS))


@pytest.fixture
def compiled(settings: Settings, transport: CountingReplay) -> Iterator[TestClient]:
    with TestClient(create_app(settings, transport=transport)) as client:
        job = client.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [0]})
        wait_for_job(client, job.json()["job_id"])
        client.post("/api/sets/dev/episodes", json={"episode_ids": [ANCHOR]})
        reference_label(client, ANCHOR)
        response = client.post("/api/rubric/draft/compile", json={"description": FROZEN.text})
        assert response.status_code == 200, response.text
        yield client


def test_dragging_a_threshold_changes_the_counts_with_zero_meta_calls(
    compiled: TestClient, transport: CountingReplay, settings: Settings
):
    draft = compiled.get("/api/rubric/draft").json()
    pauses = next(c for c in draft["criteria"] if c["primitive"] == "longest_still_s")
    calls, costs = transport.calls, settings.cost_log_path.read_text()
    assert calls > 0  # ingest and compile went through it

    def pause_counts(threshold: float) -> tuple[int, int, int]:
        edit = {"criteria": {pauses["id"]: {"threshold": threshold}}}
        preview = compiled.post("/api/rubric/draft/preview", json=edit).json()
        found = next(c for c in preview["criteria"] if c["criterion_id"] == pauses["id"])
        return found["passing"], found["failing"], found["unsure"]

    # The anchor Episode's arm is never still, so a threshold dragged to 0 s makes it unsure.
    dragged = [pause_counts(t) for t in (5.0, 2.0, 1.0, 0.5, 0.0)]
    compiled.patch("/api/rubric/draft", json={"criteria": {pauses["id"]: {"threshold": 0.0}}})

    assert dragged[0] == (1, 0, 0)
    assert dragged[-1] == (0, 0, 1)  # near threshold
    assert (transport.calls, settings.cost_log_path.read_text()) == (calls, costs)
    asked = len(transport.formats)
    compiled.post("/api/rubric/draft/run")
    reasons = compiled.get("/api/jobs/latest", params={"kind": "reason"}).json()
    wait_for_job(compiled, reasons["id"])
    assert set(transport.formats[asked:]) <= {"reason"}  # Run asks Spark only for Reasons


WITHIN_TWO = "grasps the object within two tries"


def test_editing_one_phrase_recompiles_that_phrase_only_and_re_sorts(
    compiled: TestClient, transport: CountingReplay
):
    before = compiled.get("/api/rubric/draft").json()
    [grasps] = [c["id"] for c in before["criteria"] if c["primitive"] == "grasp_attempts"]
    compiled.patch("/api/rubric/draft", json={"criteria": {grasps: {"threshold": 0}}})
    assert compiled.post("/api/rubric/draft/preview", json={}).json()["reject"] == 1
    compiles = len(transport.compiles)

    response = compiled.post("/api/rubric/draft/compile", json={"description": EDITED})

    assert response.status_code == 200, response.text
    [[prompt]] = transport.compiles[compiles:]  # one call, and no repair turn
    asked = prompt[prompt.index("Answer only for the changed text") :]
    assert asked.endswith(f'- "{WITHIN_TWO}"')  # the edited Phrase, and nothing else
    draft = response.json()
    assert [r["text"] for r in draft["recompiled"]] == [WITHIN_TWO]

    def unchanged(criteria: list[dict[str, str]]) -> list[tuple[str, str]]:
        return [(c["id"], c["phrase"]) for c in criteria if c["primitive"] != "grasp_attempts"]

    assert len(unchanged(draft["criteria"])) == 3
    assert unchanged(draft["criteria"]) == unchanged(before["criteria"])
    [grasp] = [c for c in draft["criteria"] if c["phrase"] == WITHIN_TWO]
    assert draft["english"][grasp["id"]] == "Grasp attempts, up to and including the grasp, ≤ 2"
    calls = transport.calls
    preview = compiled.post("/api/rubric/draft/preview", json={}).json()
    assert (preview["reject"], preview["needs_review"]) == (0, 1)  # re-sorted, with no call
    assert transport.calls == calls
