"""Editing the Description recompiles only the changed Phrases: one Spark call about the changed
text, with every unchanged Phrase, its Criteria (ids and edits) and its labels kept."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import app_context, reference_label, wait_for_job
from tests.rubric.scripted import ScriptedCompile, criterion, phrase
from winnow.app import create_app
from winnow.core.settings import Settings
from winnow.rubric.models import CriterionEdit, DraftEdit
from winnow.rubric.service import edit_draft

DESCRIPTION = "Tidy pick: one grasp only, gently lowered, and no long pauses."
ONE_GRASP = "one grasp only"
LOWERED = "gently lowered"
NO_PAUSES = "no long pauses"
PAUSES_FINE = "pauses are fine"
EDITED = DESCRIPTION.replace(NO_PAUSES, PAUSES_FINE)
EPISODE = "droid_100:0"
MARKER = "The curator edited this Description"  # opens a recompile's own instructions


@pytest.fixture
def spark() -> ScriptedCompile:
    return ScriptedCompile(answers=[])


PAUSES = phrase(
    NO_PAUSES, criteria=[criterion("longest_still_s", "<", 2.0, params={"speed_below_m_s": 0.01})]
)
FINE = phrase(PAUSES_FINE, "context", reason="It allows pauses.")
PAUSES_ARE_FINE = {"phrases": [FINE]}


def full_answer(last: dict[str, object] = PAUSES) -> dict[str, object]:
    return {
        "phrases": [
            phrase("Tidy pick", "context", reason="Names the task."),
            phrase(ONE_GRASP, criteria=[criterion("grasp_attempts", "<=", 1)]),
            phrase(LOWERED, criteria=[criterion("release_height_m", "<=", 0.1)]),
            last,
        ]
    }


@pytest.fixture
def drafted(settings: Settings, spark: ScriptedCompile) -> Iterator[TestClient]:
    with TestClient(create_app(settings, transport=spark)) as client:
        job = client.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [0]})
        wait_for_job(client, job.json()["job_id"])
        client.post("/api/sets/dev/episodes", json={"episode_ids": [EPISODE]})
        reference_label(client, EPISODE)
        compile_description(client, spark, DESCRIPTION, full_answer())
        yield client


def compile_description(
    api: TestClient, spark: ScriptedCompile, description: str, *answers: object, **body: object
) -> Any:
    spark.answers.extend(answers)
    response = api.post("/api/rubric/draft/compile", json={"description": description, **body})
    assert response.status_code == 200, response.text
    return response.json()


def ids_by_phrase(draft: Any) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for c in draft["criteria"]:
        found.setdefault(c["phrase"], []).append(c["id"])
    return found


def test_editing_one_phrase_asks_spark_about_that_phrase_only(
    drafted: TestClient, spark: ScriptedCompile
):
    draft = compile_description(drafted, spark, EDITED, PAUSES_ARE_FINE)

    assert len(spark.prompts) == 2  # the first compile, then one call for the edit
    [prompt] = spark.prompts[1]
    asked = prompt[prompt.index(MARKER) :]
    assert all(f'- "{kept}"' in asked for kept in ("Tidy pick", ONE_GRASP, LOWERED))
    assert asked.endswith(f'- "{PAUSES_FINE}"')  # the only text it answers for
    assert EDITED in prompt  # it reads the whole Description, as in a full compile
    assert [r["text"] for r in draft["recompiled"]] == [PAUSES_FINE]
    assert [(p["text"], p["status"]) for p in draft["phrases"]] == [
        ("Tidy pick", "context"),
        (ONE_GRASP, "checked"),
        (LOWERED, "checked"),
        (PAUSES_FINE, "context"),
    ]
    assert [c["primitive"] for c in draft["criteria"]] == ["grasp_attempts", "release_height_m"]


def test_unchanged_criteria_keep_their_ids_and_edits(drafted: TestClient, spark: ScriptedCompile):
    before = ids_by_phrase(drafted.get("/api/rubric/draft").json())
    [grasps], [lowered] = before[ONE_GRASP], before[LOWERED]
    edit = {"criteria": {grasps: {"threshold": 2}, lowered: {"enabled": False}}}
    assert drafted.patch("/api/rubric/draft", json=edit).status_code == 200

    draft = compile_description(drafted, spark, EDITED, PAUSES_ARE_FINE)

    assert ids_by_phrase(draft) == {ONE_GRASP: [grasps], LOWERED: [lowered]}
    assert next(c for c in draft["criteria"] if c["id"] == grasps)["threshold"] == 2
    assert draft["disabled"] == [lowered]


def test_a_clause_inserted_between_two_phrases_keeps_both_with_their_edits(
    drafted: TestClient, spark: ScriptedCompile
):
    before = ids_by_phrase(drafted.get("/api/rubric/draft").json())
    [grasps], [lowered] = before[ONE_GRASP], before[LOWERED]
    edit = {"criteria": {grasps: {"threshold": 2}, lowered: {"hard": False, "threshold": 0.2}}}
    assert drafted.patch("/api/rubric/draft", json=edit).status_code == 200
    inserted = DESCRIPTION.replace(f"{ONE_GRASP}, ", f"{ONE_GRASP}, never dropped, ")

    draft = compile_description(
        drafted,
        spark,
        inserted,
        {"phrases": [phrase("never dropped", "context", reason="Said elsewhere.")]},
    )

    assert spark.prompts[1][0].endswith('- "never dropped"')  # the only text it answers for
    assert [r["text"] for r in draft["recompiled"]] == ["never dropped"]
    assert ids_by_phrase(draft) == before
    by_id = {c["id"]: c for c in draft["criteria"]}
    assert by_id[grasps]["threshold"] == 2
    assert (by_id[lowered]["hard"], by_id[lowered]["threshold"]) == (False, 0.2)


def test_a_recompiled_criterion_gets_an_id_no_earlier_criterion_had(
    drafted: TestClient, spark: ScriptedCompile
):
    over_3_s = "no pauses over 3 s"
    pauses = criterion("longest_still_s", "<=", 3.0, params={"speed_below_m_s": 0.01})
    before = drafted.get("/api/rubric/draft").json()

    draft = compile_description(
        drafted,
        spark,
        DESCRIPTION.replace(NO_PAUSES, over_3_s),
        {"phrases": [phrase(over_3_s, criteria=[pauses])]},
    )

    [new] = ids_by_phrase(draft)[over_3_s]
    assert new not in {c["id"] for c in before["criteria"]}
    assert new == "longest-still-s-2"


def test_labels_on_unchanged_phrases_survive_and_on_an_edited_phrase_detach(
    drafted: TestClient, spark: ScriptedCompile
):
    assert drafted.post("/api/rubric/draft/run").status_code == 201
    for labelled in (ONE_GRASP, NO_PAUSES):
        body = {"phrase": labelled, "value": "fail", "source": "review"}
        saved = drafted.post(f"/api/episodes/{EPISODE}/labels", json=body)
        assert saved.status_code == 201, saved.text

    compile_description(drafted, spark, EDITED, PAUSES_ARE_FINE)
    assert drafted.post("/api/rubric/draft/run").status_code == 201

    triage = drafted.get(f"/api/episodes/{EPISODE}/triage").json()
    labels = {p["phrase"]: p["label"] and p["label"]["value"] for p in triage["phrases"]}
    assert labels == {"Tidy pick": None, ONE_GRASP: "fail", LOWERED: None, PAUSES_FINE: None}
    history = drafted.get(f"/api/episodes/{EPISODE}/labels").json()
    assert [label["phrase"] for label in history] == [ONE_GRASP, NO_PAUSES]  # kept, not applied


def test_deleting_a_phrase_makes_no_call(drafted: TestClient, spark: ScriptedCompile):
    draft = compile_description(drafted, spark, "Tidy pick: one grasp only, and no long pauses.")

    assert len(spark.prompts) == 1
    assert draft["recompiled"] == []
    assert [p["text"] for p in draft["phrases"]] == ["Tidy pick", ONE_GRASP, NO_PAUSES]
    assert [c["primitive"] for c in draft["criteria"]] == ["grasp_attempts", "longest_still_s"]


def test_a_phrase_spark_gives_for_unchanged_text_never_replaces_the_kept_one(
    drafted: TestClient, spark: ScriptedCompile
):
    redone = phrase(ONE_GRASP, criteria=[criterion("grasp_attempts", "<=", 5)])
    first = {"phrases": [redone, FINE]}

    draft = compile_description(drafted, spark, EDITED, first, {"phrases": [redone]})

    assert len(spark.prompts) == 3  # the edit and its one repair turn
    assert "overlaps another Phrase" in spark.prompts[2][2]
    grasps = next(c for c in draft["criteria"] if c["phrase"] == ONE_GRASP)
    assert grasps["threshold"] == 1
    assert [r["text"] for r in draft["rejected"]] == [ONE_GRASP]


def test_compiling_an_unchanged_description_compiles_it_afresh(
    drafted: TestClient, spark: ScriptedCompile
):
    [grasps] = ids_by_phrase(drafted.get("/api/rubric/draft").json())[ONE_GRASP]
    drafted.patch("/api/rubric/draft", json={"criteria": {grasps: {"threshold": 2}}})

    draft = compile_description(drafted, spark, DESCRIPTION)

    assert len(spark.prompts) == 1  # the same request again: a Meta cache hit
    assert draft["recompiled"] is None
    assert next(c for c in draft["criteria"] if c["id"] == grasps)["threshold"] == 1


def test_a_fresh_compile_ignores_the_draft(drafted: TestClient, spark: ScriptedCompile):
    draft = compile_description(drafted, spark, EDITED, full_answer(FINE), fresh=True)

    assert MARKER not in spark.prompts[1][0]
    assert draft["recompiled"] is None
    assert len(draft["phrases"]) == 4


def test_an_edit_made_while_spark_reads_the_change_survives_it(
    drafted: TestClient, spark: ScriptedCompile
):
    ctx = app_context(drafted)
    [grasps] = ids_by_phrase(drafted.get("/api/rubric/draft").json())[ONE_GRASP]
    softened = {grasps: CriterionEdit(threshold=3, hard=False)}
    spark.while_reading = lambda: edit_draft(ctx, DraftEdit(criteria=softened))

    draft = compile_description(drafted, spark, EDITED, PAUSES_ARE_FINE)

    grasp = next(c for c in draft["criteria"] if c["id"] == grasps)
    assert (grasp["threshold"], grasp["hard"]) == (3, False)
    assert [p["text"] for p in draft["phrases"]][-1] == PAUSES_FINE
    assert drafted.get("/api/rubric/draft").json()["criteria"] == draft["criteria"]


def test_a_description_compiled_while_spark_reads_the_change_is_never_overwritten(
    drafted: TestClient, spark: ScriptedCompile
):
    ctx = app_context(drafted)
    other = f"{DESCRIPTION} Quickly."

    def compiled_meanwhile() -> None:
        draft = ctx.drafts.get()
        assert draft is not None
        ctx.drafts.save(draft.model_copy(update={"description": other}))

    spark.while_reading = compiled_meanwhile
    spark.answers.append(PAUSES_ARE_FINE)

    response = drafted.post("/api/rubric/draft/compile", json={"description": EDITED})

    assert response.status_code == 409, response.text
    assert "changed while" in response.json()["detail"]
    assert drafted.get("/api/rubric/draft").json()["description"] == other
