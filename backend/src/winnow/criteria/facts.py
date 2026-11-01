"""An Episode's facts: everything the scoring function may read about one Episode.

Robot data, SAM's object tracks and the target box, Spark's stored answers to visual Criteria,
and which sources are missing or failed their step.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cached_property
from typing import Literal

from winnow.criteria.primitives import Source
from winnow.episodes.models import EpisodeSignals, FloatArray
from winnow.episodes.speed import smoothed_speed
from winnow.tracking.models import TargetBox, Track
from winnow.visual.models import VisualAnswers

SourceProblem = Literal["source missing", "step failed"]


@dataclass(frozen=True)
class EpisodeFacts:
    signals: EpisodeSignals
    # Sources a Criterion can't read for this Episode; each one's Criteria are unsure.
    unavailable: Mapping[Source, SourceProblem] = field(default_factory=dict[Source, SourceProblem])
    wrist: Track | None = None  # the wrist object track, seeded from robot data
    exterior: Track | None = None  # the exterior object track, seeded from the hand-drawn box
    target: TargetBox | None = None  # where the object should end up, on the exterior track's view

    def track_for(self, source: Source) -> Track | None:
        """The track a tracked source reads; None for any other source or a missing track."""
        return {"wrist track": self.wrist, "exterior track": self.exterior}.get(source)

    # Spark's answers to each visual Criterion asked of this Episode, by `visual.keys.ask_key`.
    visual: Mapping[str, VisualAnswers] = field(default_factory=dict[str, VisualAnswers])

    @cached_property
    def t(self) -> list[float]:
        """s from the Episode's start, per frame."""
        stamps = self.signals.timestamps
        start = float(stamps[0]) if len(stamps) else 0.0
        return [round(float(v) - start, 4) for v in stamps]

    @cached_property
    def speed(self) -> FloatArray:
        return smoothed_speed(self.signals)
