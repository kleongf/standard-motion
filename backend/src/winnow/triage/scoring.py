"""The one pure scoring function: (Rubric, Episode facts, labels, margin multiplier s) -> Triage.

Every route, preview, queue and evaluation calls `score`; nothing downstream of the Meta cache
is stored, so a changed threshold or a new label re-sorts every Episode with no model call.
"""

from collections.abc import Sequence

from winnow.criteria.catalog import CATALOG
from winnow.criteria.english import english
from winnow.criteria.facts import EpisodeFacts, SourceProblem
from winnow.criteria.grasps import Grasps, Interval, find_grasps
from winnow.criteria.measured import Measurement
from winnow.criteria.models import Criterion, Status, TextSpan, Window
from winnow.criteria.primitives import PRIMITIVES
from winnow.criteria.windows import resolve_window, window_name
from winnow.rubric.models import Rubric
from winnow.triage.confidence import (
    UNCALIBRATED,
    confidence,
    effective_margin,
    judge,
    p_keep,
    phrase_p,
)
from winnow.triage.models import (
    CriterionResult,
    Label,
    PhraseResult,
    TimeWindow,
    Triage,
    TriageDecision,
)
from winnow.triage.reason import reason_for


def score(
    rubric: Rubric, facts: EpisodeFacts, labels: Sequence[Label] = (), s: float = UNCALIBRATED
) -> Triage:
    """`s` scales every Criterion's effective margin: the Rubric version's calibrated one, or 1."""
    grasps = find_grasps(facts.signals, rubric.settings)
    results = [criterion_result(c, facts, grasps, s) for c in rubric.criteria]
    by_phrase = {label.phrase: label for label in labels}
    phrases = [
        phrase_result(p, [r for r in results if r.phrase == p], by_phrase.get(p))
        for p in rubric.phrases
    ]
    decision = weakest_link(phrases)
    keep = p_keep([p.p_pass for p in phrases if p.hard])
    return Triage(
        decision=decision,
        reason=reason_for(decision, results, phrases),
        criteria=results,
        phrases=phrases,
        p_keep=keep,
        confidence=confidence(keep),
    )


def _empty_window(window: Window, grasps: Grasps) -> Measurement:
    why = "no grasp" if grasps.grasp is None else "the grasp never opened"
    evidence = [TextSpan(text=f"No window {window_name(window)}: {why}.")]
    return Measurement(None, "no window", evidence, [], status="unsure", uncertainty="window empty")


def _unavailable(problem: SourceProblem, criterion: Criterion) -> Measurement:
    source = PRIMITIVES[criterion.primitive].source
    evidence = [TextSpan(text=f"Can't measure: {source} {problem.split()[-1]}.")]
    return Measurement(None, source, evidence, [], status="unsure", uncertainty=problem)


def _measure(
    criterion: Criterion, facts: EpisodeFacts, grasps: Grasps, frames: Interval | None
) -> Measurement:
    problem = facts.unavailable.get(PRIMITIVES[criterion.primitive].source)
    if problem is not None:
        return _unavailable(problem, criterion)
    if frames is None:
        return _empty_window(criterion.window, grasps)
    return CATALOG[criterion.primitive].measure(criterion, facts, grasps, frames)


def _camera(criterion: Criterion, facts: EpisodeFacts, measured: Measurement) -> str | None:
    """The view to show: the one Spark watched, else the Criterion's own, else its track's."""
    if measured.visual is not None and measured.visual.clip is not None:
        return measured.visual.clip.camera
    if criterion.views:
        return criterion.views[0]
    track = facts.track_for(PRIMITIVES[criterion.primitive].source)
    return None if track is None else track.camera


def criterion_result(
    criterion: Criterion, facts: EpisodeFacts, grasps: Grasps, s: float = UNCALIBRATED
) -> CriterionResult:
    frames = resolve_window(criterion.window, grasps, facts.signals.fps)
    measured = _measure(criterion, facts, grasps, frames)
    judged = judge(criterion, measured, s)
    return CriterionResult(
        criterion_id=criterion.id,
        phrase=criterion.phrase,
        primitive=criterion.primitive,
        kind=criterion.kind,
        hard=criterion.hard,
        english=english(criterion),
        status=judged.status,
        value=measured.value,
        measurement=measured.shown,
        comparator=criterion.comparator,
        threshold=criterion.threshold,
        unit=criterion.unit,
        evidence=measured.evidence,
        moments=measured.moments,
        window=None
        if frames is None
        else TimeWindow(start=facts.t[frames.start], end=facts.t[frames.end]),
        window_name=window_name(criterion.window),
        at_s=measured.at_s if judged.status == "fail" else None,
        uncertainty=judged.uncertainty,
        margin=effective_margin(criterion, s),
        p_pass=judged.p_pass,
        camera=_camera(criterion, facts, measured),
        track_plot=measured.plot,
        visual=measured.visual,
    )


def conclusive_fail(result: CriterionResult) -> bool:
    """A crisp fail that can fail its Phrase on its own."""
    return result.status == "fail" and PRIMITIVES[result.primitive].conclusive


def phrase_result(phrase: str, results: list[CriterionResult], label: Label | None) -> PhraseResult:
    """Fails on any crisp conclusive fail, passes only when all its Criteria pass, else unsure.
    Only hard Criteria decide a Phrase that has any; a human label overrides them all."""
    hard = [r for r in results if r.hard]
    deciding = hard or results
    status: Status | None = None
    p = phrase_p([r.p_pass for r in deciding])
    if label is not None:
        status = label.value
        p = 1.0 if label.value == "pass" else 0.0
    elif any(conclusive_fail(r) for r in deciding):
        status = "fail"
    elif deciding:
        status = "pass" if all(r.status == "pass" for r in deciding) else "unsure"
    return PhraseResult(phrase=phrase, hard=bool(hard), status=status, label=label, p_pass=p)


def weakest_link(phrases: list[PhraseResult]) -> TriageDecision:
    """Over hard Phrases: any fail rejects, all passing keeps, anything else needs review."""
    statuses = [p.status for p in phrases if p.hard]
    if "fail" in statuses:
        return "reject"
    return "keep" if all(s == "pass" for s in statuses) else "needs_review"
