"""Right reason: a correct Reject's Reason is right when it names a Phrase the Reference label
fails, at a time inside that Phrase's labelled interval widened by the slack. The slack is
measured, not chosen: the 95th percentile of how far the labeller's own interval edges moved
between the first pass and the relabel pass."""

import math
from collections.abc import Callable, Sequence

from winnow.evaluation.cases import Claim, EvaluationCase, failed_phrases
from winnow.evaluation.models import (
    SYSTEM_LABELS,
    RightReason,
    RightReasonRow,
    Slack,
    SlackPoint,
    System,
)
from winnow.evaluation.stats import wilson
from winnow.reference_labels.models import ReferenceLabel

SLACK_PERCENTILE = 0.95
CURVE_SLACKS = [i * 0.25 for i in range(13)]  # 0 to 3 s


def percentile(values: Sequence[float], q: float) -> float:
    """Linear interpolation between the closest ranks, as numpy's default."""
    ordered = sorted(values)
    rank = q * (len(ordered) - 1)
    low = math.floor(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (rank - low) * (ordered[high] - ordered[low])


def _edge_disagreements(first: ReferenceLabel, relabel: ReferenceLabel) -> list[float]:
    """|start - start| and |end - end| for every Phrase failed in both passes."""
    again = failed_phrases(relabel)
    return [
        abs(edge)
        for phrase, interval in failed_phrases(first).items()
        if phrase in again
        for edge in (
            interval.start_s - again[phrase].start_s,
            interval.end_s - again[phrase].end_s,
        )
    ]


def measured_slack(labels: Sequence[ReferenceLabel]) -> Slack:
    """From every relabelled Episode that also has a first pass, whatever its set: the relabel
    pass runs on the Dev set, and its slack applies to any report."""
    first = {label.episode_id: label for label in labels if not label.relabel}
    pairs = [(first[r.episode_id], r) for r in labels if r.relabel and r.episode_id in first]
    edges = [edge for a, b in pairs for edge in _edge_disagreements(a, b)]
    return Slack(
        seconds=percentile(edges, SLACK_PERCENTILE) if edges else None,
        edges=len(edges),
        episodes=len(pairs),
    )


def is_right(case: EvaluationCase, claim: Claim | None, slack_s: float) -> bool:
    """The claim names a Phrase the Reference label fails, at a time inside its widened interval.
    A Reject that names no Phrase or no time (a label-only Reject) is never right."""
    if claim is None or claim.phrase is None or claim.at_s is None:
        return False
    interval = case.failed.get(claim.phrase)
    if interval is None:
        return False
    return interval.start_s - slack_s <= claim.at_s <= interval.end_s + slack_s


# For each system scored: whether it rejected the case, and what its Reason claims.
CLAIMED_REJECTS: dict[System, Callable[[EvaluationCase], tuple[bool, Claim | None]]] = {
    "winnow": lambda c: (c.winnow == "reject", c.winnow_claim),
    "spark_alone": lambda c: (c.spark_alone == "reject", c.spark_alone_claim),
}


def _row(system: System, cases: Sequence[EvaluationCase], slack: Slack) -> RightReasonRow:
    calls = [CLAIMED_REJECTS[system](c) for c in cases]
    correct = [
        (case, claim)
        for case, (rejected, claim) in zip(cases, calls, strict=True)
        if rejected and case.description_failure
    ]

    def right(slack_s: float) -> int:
        return sum(is_right(case, claim, slack_s) for case, claim in correct)

    return RightReasonRow(
        system=system,
        label=SYSTEM_LABELS[system],
        at_slack=None if slack.seconds is None else wilson(right(slack.seconds), len(correct)),
        curve=[SlackPoint(slack_s=s, right=right(s), of=len(correct)) for s in CURVE_SLACKS],
    )


def right_reason(cases: Sequence[EvaluationCase], slack: Slack) -> RightReason:
    """k of n over each system's correct Rejects: its Rejects of description failures."""
    return RightReason(slack=slack, rows=[_row(s, cases, slack) for s in CLAIMED_REJECTS])
