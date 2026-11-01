"""Cost per 1,000 Episodes from the cost log, and a person's minutes from the label-mode timer.

The cost log names each call's Episode in its purpose (`<step>:<Episode id>[:<more>]`), so a
set's spend is what its Episodes' steps paid; cache hits are logged at $0. The extrapolation is
per Episode of the set, so x10 for a Test set of 100: it isn't run at 1,000."""

import statistics
from collections.abc import Iterable, Sequence
from typing import Literal

from winnow.evaluation.cases import EvaluationCase
from winnow.evaluation.protocol_models import MetaCost, ReviewTime, StepCost
from winnow.evaluation.stats import wilson
from winnow.meta.costs import CostEntry

System = Literal["winnow", "spark_alone", "other"]
STEPS: dict[str, tuple[str, System]] = {
    "track_wrist": ("Wrist object track (SAM)", "winnow"),
    "track_exterior": ("Exterior object track (SAM)", "winnow"),
    "target_box": ("Target box (SAM)", "winnow"),
    "visual": ("Visual Criteria (Spark)", "winnow"),
    "baseline": ("Spark alone and the FailBench check", "spark_alone"),
    "selection": ("Selection pass (Spark)", "other"),
}
COMPILE = "compile"


def step_and_episode(purpose: str) -> tuple[str, str] | None:
    """("track_wrist", "droid_100:3") from "track_wrist:droid_100:3"; None for a purpose that
    names no Episode, such as "compile"."""
    parts = purpose.split(":")
    if len(parts) < 3:
        return None
    return parts[0], f"{parts[1]}:{parts[2]}"


def _step(step: str, entries: Sequence[tuple[str, CostEntry]]) -> StepCost:
    label, system = STEPS.get(step, (step, "other"))
    paid = [(episode, e) for episode, e in entries if e.usd > 0]
    return StepCost(
        step=step,
        label=label,
        system=system,
        calls=len(paid),
        episodes=len({episode for episode, _ in paid}),
        usd=sum(e.usd for _, e in paid),
    )


def _per_1000(usd: float, episodes: int) -> float | None:
    return usd / episodes * 1000 if episodes else None


def meta_cost(entries: Iterable[CostEntry], members: Sequence[str]) -> MetaCost:
    in_set = set(members)
    by_step: dict[str, list[tuple[str, CostEntry]]] = {}
    compile_usd = 0.0
    for entry in entries:
        compile_usd += entry.usd if entry.purpose == COMPILE else 0.0
        named = step_and_episode(entry.purpose)
        if named is not None and named[1] in in_set:
            by_step.setdefault(named[0], []).append((named[1], entry))
    steps = [_step(step, rows) for step, rows in by_step.items()]
    steps.sort(key=lambda s: list(STEPS).index(s.step) if s.step in STEPS else len(STEPS))
    winnow = sum(s.usd for s in steps if s.system == "winnow")
    spark = sum(s.usd for s in steps if s.system == "spark_alone")
    return MetaCost(
        episodes=len(members),
        winnow_usd=winnow,
        winnow_per_1000_usd=_per_1000(winnow, len(members)),
        spark_alone_usd=spark,
        spark_alone_per_1000_usd=_per_1000(spark, len(members)),
        compile_usd=compile_usd,
        steps=steps,
    )


def review_time(cases: Sequence[EvaluationCase]) -> ReviewTime:
    """Minutes saved: the timer's minutes per Episode x Episodes decided automatically."""
    minutes = statistics.fmean(c.elapsed_s / 60 for c in cases) if cases else None
    decided = sum(c.winnow != "needs_review" for c in cases)
    review = wilson(len(cases) - decided, len(cases))
    return ReviewTime(
        timed=len(cases),
        minutes_per_episode=minutes,
        decided=decided,
        minutes_saved=None if minutes is None else minutes * decided,
        needs_review=review,
        needs_review_minutes_per_episode=None
        if minutes is None
        else minutes * review.count / review.of,
    )
