"""The `ask_video` primitive in the scoring function: Spark's stored samples become a Criterion
result. A unanimous answer is conclusive; a 2–1 split is unsure ("samples split"), and so is any
sample that answered unsure ("Spark said unsure").

p = (passing + 1) / (K + 2), with Spark's stated confidence breaking ties between Episodes whose
samples agree equally.
"""

from collections import Counter
from collections.abc import Sequence

from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.grasps import Grasps, Interval
from winnow.criteria.measured import Measurement
from winnow.criteria.models import Criterion, Moment, Status, TextSpan, UncertaintySignal
from winnow.visual.keys import ask_key
from winnow.visual.models import AnswerValue, VisualAnswers, VisualReply

# How far stated confidence may move p: under half the gap one more agreeing sample makes, so it
# orders Episodes within a tally and never across tallies.
TIE_BREAK = 0.02


def agreement_p(replies: Sequence[VisualReply], k: int) -> float:
    """How likely the Criterion passes, from how many of `k` samples answered pass."""
    passing = sum(1 for r in replies if r.answer == "pass")
    signed = [{"pass": 1, "fail": -1, "unsure": 0}[r.answer] * r.confidence for r in replies]
    lean = sum(signed) / k if k else 0.0
    return (passing + 1) / (k + 2) + TIE_BREAK * lean


def tally(replies: Sequence[VisualReply]) -> str:
    """e.g. '3 pass' or '2 pass · 1 fail'."""
    counts = Counter(r.answer for r in replies)
    order: list[AnswerValue] = ["pass", "fail", "unsure"]
    return " · ".join(f"{counts[a]} {a}" for a in order if counts[a])


def _not_asked() -> Measurement:
    why = "Spark hasn't answered yet: it may still be asking, or hasn't been asked."
    evidence = [TextSpan(text=why)]
    return Measurement(
        None, "not asked", evidence, [], status="unsure", uncertainty="source missing"
    )


def _failed(answers: VisualAnswers, errors: list[str]) -> Measurement:
    why = answers.error or errors[0]
    evidence = [TextSpan(text=f"Couldn't ask Spark: {why}")]
    return Measurement(
        None,
        "step failed",
        evidence,
        [],
        status="unsure",
        uncertainty="step failed",
        visual=answers,
    )


def _judged(replies: list[VisualReply], k: int) -> tuple[Status, UncertaintySignal | None]:
    answered = {r.answer for r in replies}
    if "unsure" in answered:
        return "unsure", "Spark said unsure"
    if len(replies) < k:
        return "unsure", "step failed"
    if len(answered) > 1:
        return "unsure", "samples split"
    return ("pass" if answered == {"pass"} else "fail"), None


def _evidence(
    criterion: Criterion, answers: VisualAnswers, replies: list[VisualReply], status: Status
) -> list[TextSpan]:
    k = len(answers.samples)
    if status != "unsure":
        lead = f"All {k} samples: {status}. "
    else:
        lead = f"Samples: {tally(replies)}, of {k}. "
    evidence = [TextSpan(text=lead + (replies[0].observation if replies else ""))]
    if criterion.crop == "placement" and answers.clip is not None and answers.clip.box is None:
        why = " Asked of the whole view: no object track and target box to crop to."
        evidence.append(TextSpan(text=why))
    return evidence


def ask_video(
    criterion: Criterion, facts: EpisodeFacts, grasps: Grasps, window: Interval
) -> Measurement:
    answers = facts.visual.get(ask_key(criterion, grasps.settings))
    if answers is None or (answers.error is None and not answers.samples):
        return _not_asked()  # nothing stored, or a clip cut and not yet asked about
    k = len(answers.samples)
    replies = [s.reply for s in answers.samples if s.reply is not None]
    errors = [s.error for s in answers.samples if s.error is not None]
    if answers.error is not None or not replies:
        return _failed(answers, errors)
    status, signal = _judged(replies, k)
    start = facts.t[window.start]
    return Measurement(
        float(sum(1 for r in replies if r.answer == "pass")),
        tally(replies),
        _evidence(criterion, answers, replies, status),
        [Moment(t=start, label="Clip")],
        at_s=start,
        status=status,
        uncertainty=signal,
        p=agreement_p(replies, k),
        visual=answers,
    )
