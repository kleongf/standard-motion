"""Measured primitives about the grasp: computed from an Episode's robot data alone, no model
calls. Primitives about the arm's motion live in `criteria.motion`."""

from dataclasses import dataclass, replace

from winnow.criteria.comparison import passes
from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.grasp_margins import near_closures, readings
from winnow.criteria.grasps import Grasps, Interval
from winnow.criteria.models import (
    Criterion,
    Moment,
    Status,
    TextSpan,
    TrackPlot,
    UncertaintySignal,
)
from winnow.visual.models import VisualAnswers


@dataclass(frozen=True)
class Measurement:
    value: float | None  # in the primitive's unit; None when there is nothing to measure
    shown: str  # the value as the user reads it, e.g. "3 attempts"
    evidence: list[TextSpan]
    moments: list[Moment]
    at_s: float | None = None  # where it goes wrong, should the value fail
    status: Status | None = None  # set only when the value alone doesn't decide
    uncertainty: UncertaintySignal | None = None  # set when the measure itself is unsure
    # The signed distance from the threshold in effective margins, when the measure knows it
    # better than its value does (a count near the grasp rule).
    m: float | None = None
    plot: TrackPlot | None = None  # tracked primitives: the signal the value is read from
    p: float | None = None  # p_pass, when the measure knows it directly (Spark's agreement)
    visual: VisualAnswers | None = None  # Spark's samples and the clip, for a visual Criterion


def seconds(t: float) -> str:
    return f"{t:.1f} s"


def at_times(times: list[float]) -> list[TextSpan]:
    """'0.9 s, 1.3 s and 1.8 s', each time a span that seeks."""
    spans: list[TextSpan] = []
    for i, t in enumerate(times):
        if i:
            spans.append(TextSpan(text=" and " if i == len(times) - 1 else ", "))
        spans.append(TextSpan(text=seconds(t), t=t))
    return spans


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def grasp_attempts(
    criterion: Criterion, facts: EpisodeFacts, grasps: Grasps, window: Interval
) -> Measurement:
    """Closures up to and including the grasp. With no grasp it fails, whatever the threshold.
    Unsure when reading the closures at the edges of the Rubric settings' margins would change
    the result."""
    counted = _count_attempts(facts, grasps)
    nominal = _attempts_status(criterion, grasps)
    edges = readings(facts.signals, grasps.settings)
    if all(_attempts_status(criterion, g) == nominal for g in edges):
        return counted
    near = near_closures(facts.signals, grasps.settings)
    evidence = counted.evidence
    if near:
        evidence = [
            *evidence,
            TextSpan(text=" Unsure: the closure at "),
            *at_times([facts.t[near[0].start]]),
            TextSpan(text=f" {near[0].why}."),
        ]
    margins = near[0].margins if near else 0.0
    return replace(
        counted,
        evidence=evidence,
        status="unsure",
        uncertainty="near threshold (count)",
        m=margins if nominal == "pass" else -margins,
    )


def _attempts_status(criterion: Criterion, grasps: Grasps) -> Status:
    if grasps.grasp is None:
        return "fail"
    return "pass" if passes(criterion, len(grasps.failed) + 1) else "fail"


def _count_attempts(facts: EpisodeFacts, grasps: Grasps) -> Measurement:
    t = facts.t
    failed = [t[c.start] for c in grasps.failed]
    moments = [Moment(t=s, label=f"Attempt {i + 1}") for i, s in enumerate(failed)]
    grasp = grasps.the_grasp
    if grasp is None:
        evidence = [TextSpan(text="No grasp: the gripper never closed.")]
        if failed:
            rise = f"{grasps.rise_rule_m * 100:g} cm"
            evidence = [
                TextSpan(text=f"No grasp: {plural(len(failed), 'closure')}, at "),
                *at_times(failed),
                TextSpan(text=f", and none lifted the arm {rise}."),
            ]
        return Measurement(
            len(failed), "no grasp", evidence, moments, failed[0] if failed else None, "fail"
        )
    moments.append(Moment(t=t[grasp.start], label="Grasp"))
    if not failed:
        evidence = [TextSpan(text="Grasped on the first closure, at "), *at_times([t[grasp.start]])]
        return Measurement(1, "1 attempt", [*evidence, TextSpan(text=".")], moments)
    evidence = [
        TextSpan(text=f"{plural(len(failed), 'failed grasp attempt')}, at "),
        *at_times(failed),
        TextSpan(text=", before the grasp at "),
        *at_times([t[grasp.start]]),
        TextSpan(text="."),
    ]
    attempts = len(failed) + 1
    return Measurement(attempts, plural(attempts, "attempt"), evidence, moments, failed[0])


def release_height_m(
    criterion: Criterion, facts: EpisodeFacts, grasps: Grasps, window: Interval
) -> Measurement:
    """How far above the height it was picked up at the grasp opened; set by the grasp, not the
    window. Inconclusive: a high release is right when stacking."""
    grasp = grasps.the_grasp
    if grasp is None or not grasps.released:
        why = "No grasp to release." if grasp is None else "No release: the grasp never opened."
        return Measurement(
            None,
            "no release",
            [TextSpan(text=why)],
            [],
            status="unsure",
            uncertainty="window empty",
        )
    z = facts.signals.position[:, 2]
    released = grasp.end + 1
    height = float(z[released] - z[grasp.start])
    t = facts.t[released]
    evidence = [
        TextSpan(text=f"Released {abs(height) * 100:.1f} cm "),
        TextSpan(text=f"{'above' if height >= 0 else 'below'} where it was picked up, at "),
        *at_times([t]),
        TextSpan(text="."),
    ]
    moments = [Moment(t=t, label="Release")]
    return Measurement(round(height, 4), f"{round(height * 100, 1):g} cm", evidence, moments, t)
