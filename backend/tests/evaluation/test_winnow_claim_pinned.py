"""Pinned: right reason reads Winnow's claim from its Criterion results, never from the Reason's
text, so Spark's Reason swapped in over the template changes neither."""

import pytest
from fastapi.testclient import TestClient

from tests.evaluation.test_evaluation_api import labelled, run
from tests.helpers import app_context
from winnow.baseline.prompts import FROZEN
from winnow.criteria.models import TextSpan
from winnow.evaluation.cases import winnow_claim
from winnow.triage.service import episode_triage, template_triages
from winnow.triage.spark_reason import reason_key

FIRST_TRY = FROZEN.phrases[0]
REGRASP = "droid_100:2"  # rejected for its grasp attempts; labelled failing the whole Episode
# A Reason that names another Phrase at another time than the template's lead fail.
ELSEWHERE = [TextSpan(text="It pauses at "), TextSpan(text="2.9 s", t=2.9), TextSpan(text=".")]


def test_winnow_claim_and_right_reason_ignore_spark_s_reason(asked_api: TestClient):
    api = asked_api
    labelled(api, "dev")
    ctx = app_context(api)
    episode = ctx.episodes.get(REGRASP)
    assert episode is not None
    before = run(api, "dev")
    claim = winnow_claim(episode_triage(ctx, episode))

    version, [template] = template_triages(ctx, [episode])
    ctx.reasons.put(REGRASP, reason_key(version.version, template), ELSEWHERE)

    swapped = episode_triage(ctx, episode)
    assert (swapped.reason_source, swapped.reason) == ("spark", ELSEWHERE)
    assert winnow_claim(swapped) == claim
    assert claim is not None and claim.phrase == FIRST_TRY
    assert claim.at_s == pytest.approx(0.9, abs=0.05)  # the first failed attempt
    after = run(api, "dev")
    assert after["right_reason"] == before["right_reason"]
    assert after["comparison"] == before["comparison"]
