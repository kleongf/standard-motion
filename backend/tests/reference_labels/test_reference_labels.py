import pytest
from fastapi.testclient import TestClient

from tests.helpers import wait_for_job
from winnow.baseline.prompts import FROZEN

PHRASES = FROZEN.phrases
# droid_100:2 of the fixture source has no instruction and a failing Dataset outcome.
NO_INSTRUCTION = "droid_100:2"


@pytest.fixture
def ingested(api: TestClient) -> TestClient:
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [0, 1, 2]})
    wait_for_job(api, job.json()["job_id"])
    return api


def judgments(**fails: tuple[float, float]) -> list[dict[str, object]]:
    """Every frozen Phrase passes except those named by index, e.g. p1=(0.5, 1.2)."""
    out: list[dict[str, object]] = []
    for i, phrase in enumerate(PHRASES):
        interval = fails.get(f"p{i}")
        out.append(
            {
                "phrase": phrase,
                "passed": interval is None,
                "interval": None
                if interval is None
                else {"start_s": interval[0], "end_s": interval[1]},
            }
        )
    return out


def label(api: TestClient, episode_id: str, **body: object):
    payload = {"phrases": judgments(p1=(0.5, 1.2)), "elapsed_s": 42.5} | body
    return api.post(f"/api/episodes/{episode_id}/reference-labels", json=payload)


def labels(api: TestClient) -> list[dict[str, object]]:
    return api.get("/api/reference-labels").json()


def test_labels_are_given_against_the_frozen_description_and_its_phrases(api: TestClient):
    assert api.get("/api/reference-labels/description").json() == {
        "text": "Expert pick-and-place: grasps the object on the first try, never drops it, "
        "places it in or on the target named in the instruction, no long pauses.",
        "phrases": [
            "grasps the object on the first try",
            "never drops it",
            "places it in or on the target named in the instruction",
            "no long pauses",
        ],
    }


def test_a_saved_label_keeps_each_phrase_its_intervals_and_the_elapsed_time(
    ingested: TestClient,
):
    saved = label(ingested, "droid_100:1")

    assert saved.status_code == 201
    [stored] = labels(ingested)
    assert stored["episode_id"] == "droid_100:1"
    assert stored["relabel"] is False
    assert stored["description"] == FROZEN.text
    assert stored["phrases"] == judgments(p1=(0.5, 1.2))
    assert stored["elapsed_s"] == 42.5
    assert stored["instruction"] == ingested.get("/api/episodes").json()[1]["instruction"]


def episode(api: TestClient, episode_id: str) -> dict[str, object]:
    return next(e for e in api.get("/api/episodes").json() if e["id"] == episode_id)


def test_where_an_episode_has_no_instruction_the_labeller_writes_one(ingested: TestClient):
    assert label(ingested, NO_INSTRUCTION).status_code == 422
    assert label(ingested, NO_INSTRUCTION, instruction="  ").status_code == 422

    written = "Put the red block in the bowl"
    assert label(ingested, NO_INSTRUCTION, instruction=written).status_code == 201
    [stored] = labels(ingested)
    assert stored["instruction"] == written
    # Winnow and Spark alone read it from the Episode, never from the Reference label.
    assert episode(ingested, NO_INSTRUCTION)["instruction"] == written


def test_a_relabel_is_kept_beside_the_first_pass(ingested: TestClient):
    label(ingested, "droid_100:0", phrases=judgments(p1=(0.5, 1.2)))
    relabelled = label(ingested, "droid_100:0", phrases=judgments(p1=(0.7, 1.5)), relabel=True)

    assert relabelled.status_code == 201
    first, second = labels(ingested)
    assert (first["relabel"], first["phrases"]) == (False, judgments(p1=(0.5, 1.2)))
    assert (second["relabel"], second["phrases"]) == (True, judgments(p1=(0.7, 1.5)))


def test_a_saved_label_is_never_replaced(ingested: TestClient):
    label(ingested, "droid_100:0")
    label(ingested, "droid_100:0", relabel=True)

    assert label(ingested, "droid_100:0", phrases=judgments()).status_code == 409
    assert label(ingested, "droid_100:0", phrases=judgments(), relabel=True).status_code == 409
    assert [x["phrases"] for x in labels(ingested)] == [judgments(p1=(0.5, 1.2))] * 2


def test_a_relabel_needs_a_first_pass(ingested: TestClient):
    assert label(ingested, "droid_100:0", relabel=True).status_code == 409
    assert labels(ingested) == []


def test_the_dataset_outcome_stays_hidden_until_the_episode_is_labelled(ingested: TestClient):
    # The fixture's droid_100:1 succeeded and droid_100:2 failed.
    assert [e["dataset_outcome"] for e in ingested.get("/api/episodes").json()] == [None] * 3

    label(ingested, "droid_100:1")
    label(ingested, NO_INSTRUCTION, instruction="Put the red block in the bowl")

    outcomes = [e["dataset_outcome"] for e in ingested.get("/api/episodes").json()]
    assert outcomes == [None, True, False]


def test_only_ingested_episodes_are_labelled(ingested: TestClient):
    assert label(ingested, "droid_100:4").status_code == 404


def without_interval(index: int) -> list[dict[str, object]]:
    phrases = judgments()
    phrases[index] = {"phrase": PHRASES[index], "passed": False, "interval": None}
    return phrases


@pytest.mark.parametrize(
    "phrases",
    [
        without_interval(1),  # a fail needs the stretch where it fails
        judgments()[:3],  # every Phrase gets a judgment
        [*judgments()[:3], {"phrase": "moves fast", "passed": True, "interval": None}],
        judgments(p3=(2.0, 9.0)),  # past the end of the 3 s fixture Episode
        judgments(p3=(2.0, 1.0)),  # ends before it starts
    ],
)
def test_incomplete_labels_are_refused(ingested: TestClient, phrases: list[dict[str, object]]):
    assert label(ingested, "droid_100:1", phrases=phrases).status_code == 422
    assert labels(ingested) == []
