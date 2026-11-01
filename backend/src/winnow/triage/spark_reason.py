"""Spark's Reason: one Spark call rewrites a Reject's or Needs review's template Reason from its
Evidence, citing only times Winnow gave it. It is keyed by what decided the Episode, so a label,
a new Rubric version or new Evidence falls back to the template until Spark writes again."""

import hashlib
import json

from pydantic import BaseModel, ValidationError

from winnow.criteria.models import TextSpan
from winnow.meta.client import MetaClient
from winnow.meta.models import SparkRequest, Text
from winnow.meta.pricing import SPARK_CONTRIBUTOR
from winnow.triage.models import CriterionResult, Triage
from winnow.triage.reason import labelled_fails, rejecting_fails, undecided
from winnow.triage.reason_prompt import REASON_SCHEMA, reason_prompt, shown

MAX_OUTPUT_TOKENS = 2000  # one sentence, but low effort still reasons before it
TIME_TOLERANCE_S = 0.0015  # the prompt gives times to the millisecond


class ReasonAnswerError(RuntimeError):
    """Spark's Reason couldn't be read, or cites a time Winnow didn't give it; the template
    Reason stays."""


class _Answer(BaseModel):
    spans: list[TextSpan]


def deciding(triage: Triage) -> list[CriterionResult]:
    """The results the Triage decision rests on: a Reject's conclusive fails, earliest first, or
    the hard results keeping Needs review's unsure Phrases from passing."""
    if triage.decision == "reject":
        return rejecting_fails(triage.criteria, triage.phrases)
    if triage.decision == "needs_review":
        unsure = [p.phrase for p in triage.phrases if p.hard and p.status == "unsure"]
        return [r for phrase in unsure for r in undecided(triage.criteria, phrase)]
    return []


def reason_key(version: int, triage: Triage) -> str:
    """What a Spark Reason was written from: the Rubric version, the deciding results and
    labels, and the prompt itself, which holds the Triage decision, the template Reason and every
    time Spark may cite. Pass the template triage."""
    results = deciding(triage)
    named = {r.phrase for r in results} | {p.phrase for p in labelled_fails(triage.phrases)}
    written = {
        "version": version,
        "results": [[r.criterion_id, r.status, r.value] for r in results],
        "labels": [
            [p.phrase, p.label.value, p.label.source]
            for p in triage.phrases
            if p.phrase in named and p.label is not None
        ],
        "prompt": reason_prompt(triage),
    }
    canonical = json.dumps(written, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:24]


def given_times(triage: Triage) -> list[float]:
    """Every time the prompt gives Spark: the template's, and each shown result's Evidence,
    moments and where it went wrong."""
    times = [s.t for s in triage.reason]
    for result in shown(triage):
        times += [s.t for s in result.evidence] + [m.t for m in result.moments] + [result.at_s]
    return sorted({t for t in times if t is not None})


def _given(t: float, times: list[float]) -> float:
    """The given time nearest the one Spark cited; raises if none is within the tolerance."""
    nearest = min(times, key=lambda g: abs(g - t), default=None)
    if nearest is None or abs(nearest - t) > TIME_TOLERANCE_S:
        raise ReasonAnswerError(f"Spark cited {t} s, a time it wasn't given")
    return nearest


def _checked(answer: str, triage: Triage) -> list[TextSpan]:
    try:
        spans = _Answer.model_validate_json(answer).spans
    except ValidationError as error:
        raise ReasonAnswerError(f"Spark's Reason couldn't be read: {error}") from error
    if not spans:
        raise ReasonAnswerError("Spark wrote an empty Reason")
    times = given_times(triage)
    spans = [s if s.t is None else TextSpan(text=s.text, t=_given(s.t, times)) for s in spans]
    fails = deciding(triage) if triage.decision == "reject" else []
    lead = fails[0].at_s if fails else None
    first = next((s.t for s in spans if s.t is not None), None)
    if lead is not None and first != lead:
        raise ReasonAnswerError(f"Spark's Reason doesn't lead with the fail at {lead:.3f} s")
    return spans


async def write_reason(meta: MetaClient, triage: Triage, episode_id: str) -> list[TextSpan]:
    """Spark's Reason for a Reject or Needs review, from its template triage."""
    request = SparkRequest(
        SPARK_CONTRIBUTOR,
        (Text(reason_prompt(triage)),),
        REASON_SCHEMA,
        f"reason:{episode_id}",
        effort="low",
        max_output_tokens=MAX_OUTPUT_TOKENS,
        schema_name="reason",
    )
    reply = await meta.spark(request)
    return _checked(reply.text, triage)
