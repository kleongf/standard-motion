"""Synthetic robot data and Rubrics for scoring-function tests, at 15 Hz."""

from collections.abc import Sequence

import numpy as np

from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.models import Criterion, RubricSettings, Setting, Window
from winnow.episodes.models import EpisodeSignals
from winnow.rubric.models import Rubric
from winnow.triage.models import Triage

FIRST_TRY = "grasps the object on the first try"
PLACES = "places it on the target"
NO_PAUSES = "no long pauses"
SETTINGS = RubricSettings(
    gripper_closed_level=Setting(value=0.2, margin=0.1),
    grasp_rise_m=Setting(value=0.02, margin=0.01),
)
UP, DOWN = 0.10, 0.0  # end-effector heights, m


def facts(
    gripper: Sequence[float], z: Sequence[float] | None = None, x: Sequence[float] | None = None
) -> EpisodeFacts:
    """By default the arm keeps moving along x, so it is never still."""
    n = len(gripper)
    zs = np.asarray(z if z is not None else [DOWN] * n, dtype=np.float64)
    xs = np.asarray(x if x is not None else np.linspace(0, 1, n), dtype=np.float64)
    position = np.stack([xs, np.zeros(n), zs], axis=1)
    signals = EpisodeSignals(
        episode_index=0,
        fps=15.0,
        timestamps=np.arange(n) / 15.0,
        position=position,
        gripper=np.asarray(gripper, dtype=np.float64),
        dataset_outcome=True,
    )
    return EpisodeFacts(signals)


def frames(*runs: tuple[float, int]) -> list[float]:
    return [value for value, count in runs for _ in range(count)]


def first_try(threshold: float = 1, hard: bool = True, id: str = "grasp-attempts") -> Criterion:
    return Criterion(
        id=id,
        phrase=FIRST_TRY,
        primitive="grasp_attempts",
        comparator="<=",
        threshold=threshold,
        unit="attempts",
        hard=hard,
    )


def still(
    phrase: str = NO_PAUSES,
    window: Window | None = None,
    hard: bool = True,
    id: str = "still",
    threshold: float = 1.0,
    margin: float = 0.0,
) -> Criterion:
    return Criterion(
        id=id,
        phrase=phrase,
        primitive="longest_still_s",
        params={"speed_below_m_s": 0.01},
        comparator="<",
        threshold=threshold,
        unit="s",
        margin=margin,
        window=window or Window(),
        hard=hard,
    )


def release(threshold: float = 0.05, margin: float = 0.0) -> Criterion:
    return Criterion(
        id="release-height",
        phrase=PLACES,
        primitive="release_height_m",
        comparator="<=",
        threshold=threshold,
        unit="m",
        margin=margin,
    )


def rubric(*criteria: Criterion, settings: RubricSettings = SETTINGS) -> Rubric:
    return Rubric(
        description=f"Expert: {FIRST_TRY}, {PLACES}, {NO_PAUSES}.",
        phrases=[FIRST_TRY, PLACES, NO_PAUSES],
        settings=settings,
        criteria=list(criteria),
    )


def text(triage: Triage) -> str:
    return "".join(span.text for span in triage.reason)


# One closure (frames 15-29) during which the arm lifts 10 cm, then it opens.
CLEAN_GRIPPER = frames((0, 15), (1, 15), (0, 15))
CLEAN_Z = frames((DOWN, 20), (UP, 25))
# Episode 42's shape: two closures that don't lift (frames 10-14, 20-24), then the grasp
# (frames 30-44) that does. 3.0 s at 15 Hz.
REGRASP_GRIPPER = frames((0, 10), (1, 5), (0, 5), (1, 5), (0, 5), (1, 15))
REGRASP_Z = frames((DOWN, 35), (UP, 10))
