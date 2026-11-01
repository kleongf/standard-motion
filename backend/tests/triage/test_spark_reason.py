"""Spark's Reason: what it is keyed by, and which answers are kept."""

import asyncio
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from tests.meta.fakes import FakeTransport
from tests.triage.robot_data import (
    FIRST_TRY,
    REGRASP_GRIPPER,
    REGRASP_Z,
    facts,
    first_try,
    rubric,
)
from winnow.core.db import open_db
from winnow.meta.client import MetaClient
from winnow.meta.costs import CostLog
from winnow.meta.transport import Reply
from winnow.triage.models import Label, Triage
from winnow.triage.scoring import score
from winnow.triage.spark_reason import ReasonAnswerError, reason_key, write_reason


def regrasp(*labels: Label) -> Triage:
    """Episode 42's shape: rejected for two failed grasp attempts before the grasp."""
    return score(rubric(first_try()), facts(REGRASP_GRIPPER, REGRASP_Z), labels)


def test_the_key_is_the_same_for_the_same_inputs():
    assert reason_key(1, regrasp()) == reason_key(1, regrasp())


def test_a_new_rubric_version_or_a_label_changes_the_key():
    key = reason_key(1, regrasp())

    assert reason_key(2, regrasp()) != key
    labelled = regrasp(Label(phrase=FIRST_TRY, value="fail", source="review"))
    assert labelled.decision == "reject"
    assert reason_key(1, labelled) != key


def test_any_time_spark_is_shown_moving_changes_the_key():
    triage = regrasp()
    [result] = triage.criteria
    moved = [m.model_copy(update={"t": m.t + 0.2}) for m in result.moments]
    elsewhere = triage.model_copy(
        update={"criteria": [result.model_copy(update={"moments": moved})]}
    )

    assert reason_key(1, elsewhere) != reason_key(1, triage)


def answering(
    tmp_path: Path, spans: Sequence[Mapping[str, object]]
) -> tuple[MetaClient, FakeTransport]:
    transport = FakeTransport(reply=Reply(json.dumps({"spans": spans}), {"input_tokens": 900}))
    costs = CostLog(tmp_path / "meta_costs.jsonl", 5.0)
    return MetaClient(transport, open_db(tmp_path / "winnow.db"), costs), transport


def test_spark_s_reason_is_kept_when_it_cites_only_given_times(tmp_path: Path):
    triage = regrasp()
    first, second, grasp = (m.t for m in triage.criteria[0].moments)
    spans = [
        {"text": "Two grasps slipped, at ", "t": None},
        {"text": "0.7 s", "t": first},
        {"text": " and ", "t": None},
        {"text": "1.3 s", "t": second},
        {"text": ", before it held at ", "t": None},
        {"text": "2.0 s", "t": grasp},
        {"text": ".", "t": None},
    ]
    meta, transport = answering(tmp_path, spans)

    written = asyncio.run(write_reason(meta, triage, "droid_100:2"))

    assert [(s.text, s.t) for s in written] == [(s["text"], s["t"]) for s in spans]
    [(_, content)] = transport.calls
    prompt = str(content[0]["text"])
    assert "2 failed grasp attempts" in prompt
    assert f"t={first:.3f}" in prompt


def test_a_time_spark_rounded_is_read_as_the_time_it_was_given(tmp_path: Path):
    triage = regrasp()
    first = triage.criteria[0].moments[0].t
    meta, _ = answering(tmp_path, [{"text": "It slipped at 0.7 s.", "t": round(first, 3)}])

    [written] = asyncio.run(write_reason(meta, triage, "droid_100:2"))

    assert written.t == first


def test_a_time_winnow_didnt_give_is_rejected(tmp_path: Path):
    meta, _ = answering(tmp_path, [{"text": "It slipped at 0.5 s.", "t": 0.5}])

    with pytest.raises(ReasonAnswerError, match=r"0\.5"):
        asyncio.run(write_reason(meta, regrasp(), "droid_100:2"))


def test_a_reject_leads_with_where_its_earliest_conclusive_fail_went_wrong(tmp_path: Path):
    triage = regrasp()
    first, _, grasp = (m.t for m in triage.criteria[0].moments)
    spans = [
        {"text": "It held at 2.0 s ", "t": grasp},
        {"text": "after slipping at 0.7 s", "t": first},
    ]
    meta, _ = answering(tmp_path, spans)

    with pytest.raises(ReasonAnswerError, match="lead"):
        asyncio.run(write_reason(meta, triage, "droid_100:2"))


def test_an_answer_that_cant_be_read_is_rejected(tmp_path: Path):
    meta, _ = answering(tmp_path, [{"words": "Rejected."}])

    with pytest.raises(ReasonAnswerError):
        asyncio.run(write_reason(meta, regrasp(), "droid_100:2"))
