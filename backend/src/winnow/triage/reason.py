"""Template Reasons: one sentence per Episode, written from its results the moment they exist.

A Reject leads with its earliest-in-time conclusive fail and lists the others after it; a
label-only Reject names the labelled Phrase and its source; Needs review lists its Uncertainty
signals.
"""

from winnow.criteria.english import COMPARATORS, format_value
from winnow.criteria.measured import at_times
from winnow.criteria.models import TextSpan
from winnow.criteria.primitives import PRIMITIVES
from winnow.triage.models import CriterionResult, PhraseResult, TriageDecision


def rejecting_fails(
    results: list[CriterionResult], phrases: list[PhraseResult]
) -> list[CriterionResult]:
    """Conclusive fails of hard Criteria whose Phrase failed, earliest first (untimed last)."""
    failed = {p.phrase for p in phrases if p.hard and p.status == "fail"}
    fails = [
        r
        for r in results
        if r.hard
        and r.phrase in failed
        and r.status == "fail"
        and PRIMITIVES[r.primitive].conclusive
    ]
    return sorted(fails, key=lambda r: (r.at_s is None, r.at_s or 0.0))


def labelled_fails(phrases: list[PhraseResult]) -> list[PhraseResult]:
    """Hard Phrases a human label failed, in Rubric order: what a label-only Reject names."""
    return [p for p in phrases if p.hard and p.status == "fail" and p.label is not None]


def _reject(results: list[CriterionResult], phrases: list[PhraseResult]) -> list[TextSpan]:
    fails = rejecting_fails(results, phrases)
    labelled = labelled_fails(phrases)
    if not fails:
        first = labelled[0]
        source = first.label.source if first.label else "review"
        return [TextSpan(text=f'Rejected: "{first.phrase}" was marked fail in {source}.')]
    lead, *others = fails
    spans = [TextSpan(text=f'Rejected: "{lead.phrase}" failed. '), *lead.evidence]
    for i, other in enumerate(others):
        spans.append(
            TextSpan(text=f' Also failed: "{other.phrase}"' if i == 0 else f'; "{other.phrase}"')
        )
        if other.at_s is not None:
            spans += [TextSpan(text=" at "), *at_times([other.at_s])]
    if others:
        spans.append(TextSpan(text="."))
    return spans


def _detail(result: CriterionResult) -> str:
    """What the signal is about: the measurement against its threshold, the empty window, or
    what couldn't be measured."""
    if result.value is None:
        return result.window_name if result.measurement == "no window" else result.measurement
    if result.kind == "visual":  # Spark's tally; it has no threshold to compare against
        return result.measurement
    threshold = format_value(result.threshold, result.unit)
    return f"{result.measurement} against {COMPARATORS[result.comparator]} {threshold}"


def signal_text(result: CriterionResult) -> str:
    """Why a result isn't a pass, e.g. "near threshold (4.4 cm against ≤ 5 cm)"."""
    return f"{result.uncertainty or result.status} ({_detail(result)})"


def undecided(results: list[CriterionResult], phrase: str) -> list[CriterionResult]:
    """The hard results that keep an unsure Phrase from passing."""
    return [r for r in results if r.phrase == phrase and r.hard and r.status != "pass"]


def _needs_review(results: list[CriterionResult], phrases: list[PhraseResult]) -> list[TextSpan]:
    """Each unsure hard Phrase's Uncertainty signals, in Rubric order."""
    unsure = [p.phrase for p in phrases if p.hard and p.status == "unsure"]
    signals = [f'"{p}": {signal_text(r)}' for p in unsure for r in undecided(results, p)]
    return [TextSpan(text=f"Needs review: {'; '.join(dict.fromkeys(signals))}.")]


def reason_for(
    decision: TriageDecision, results: list[CriterionResult], phrases: list[PhraseResult]
) -> list[TextSpan]:
    if decision == "reject":
        return _reject(results, phrases)
    if decision == "needs_review":
        return _needs_review(results, phrases)
    checked = sum(1 for p in phrases if p.hard)
    if checked == 0:
        return [TextSpan(text="Kept: no hard Criterion checks this Rubric's Phrases.")]
    return [TextSpan(text="Kept: every hard Phrase passed.")]
