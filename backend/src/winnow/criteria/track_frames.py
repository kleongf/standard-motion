"""What the tracked primitives share: the stretch of a SAM track's 5 fps frames a Criterion reads,
the track's health over it, and the results a missing or lost track gives.

Health is `tracking.health`'s three rules, judged only on the frames the Criterion reads, so a
track lost elsewhere in the Episode never makes it unsure.
"""

import statistics
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Self

from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.measured import Measurement, at_times
from winnow.criteria.models import PlotPoint, TextSpan, TrackPlot
from winnow.tracking.health import MISSING_FRACTION, track_health
from winnow.tracking.models import Track, TrackBox, TrackHealth, TrackKind


def frame_at(track: Track, t: float) -> int:
    """The 5 fps frame showing at `t` s."""
    return max(0, min(int(t * track.fps + 1e-6), track.frames - 1))


def frame_time(track: Track, frame: int) -> float:
    return round(frame / track.fps, 4)


def robot_frame(facts: EpisodeFacts, t: float) -> int:
    """The robot-data frame nearest `t` s."""
    return max(0, min(round(t * facts.signals.fps), len(facts.t) - 1))


def centre(box: TrackBox) -> tuple[float, float]:
    return ((box.left + box.right) / 2, (box.top + box.bottom) / 2)


def median_width(track: Track) -> float:
    return statistics.median(b.right - b.left for b in track.boxes) if track.boxes else 1.0


def no_track(kind: TrackKind, why: str) -> Measurement:
    """A Criterion whose track doesn't exist: unsure, with nothing measured."""
    evidence = [TextSpan(text=f"No {kind} track: {why}")]
    return Measurement(
        None, f"no {kind} track", evidence, [], status="unsure", uncertainty="source missing"
    )


@dataclass(frozen=True)
class Stretch:
    """The 5 fps frames of a track that a Criterion reads, and SAM's boxes on them."""

    track: Track
    frames: range
    boxes: Mapping[int, TrackBox]  # by frame, only those in `frames`

    @classmethod
    def read(cls, track: Track, facts: EpisodeFacts, start: int, end: int) -> Self:
        """The frames covering robot-data frames `start` to `end`, inclusive."""
        frames = range(frame_at(track, facts.t[start]), frame_at(track, facts.t[end]) + 1)
        return cls(track, frames, {b.frame: b for b in track.boxes if b.frame in frames})

    @property
    def seen(self) -> list[int]:
        """The frames SAM found a box on, in order."""
        return [f for f in self.frames if f in self.boxes]

    def time(self, frame: int) -> float:
        return frame_time(self.track, frame)

    def plot(
        self, label: str, unit: str, level: float, values: Mapping[int, float | None]
    ) -> TrackPlot:
        """A point per frame; no value where `values` has none (SAM had no box)."""
        points = [PlotPoint(t=self.time(f), value=values.get(f)) for f in self.frames]
        return TrackPlot(label=label, unit=unit, level=level, points=points)

    def judged(
        self,
        measured: Measurement,
        plot: TrackPlot | None,
        health_on: range | None = None,
        falls_ok: bool = False,
    ) -> Measurement:
        """`measured` with its plot, made unsure if SAM lost the object on `health_on` (the
        whole stretch by default). With `falls_ok`, a centre jump straight down is a fall, not a
        loss. A lost track's value stays for the record, but carries no weight: p is 0.5."""
        measured = replace(measured, plot=plot)
        health = track_health(self.track.boxes, self.track.frames, health_on or self.frames)
        if falls_ok:
            health = self._without_falls(health)
        if not health.lost:
            return measured
        evidence = [
            *measured.evidence,
            TextSpan(text=" Unsure: SAM lost the object here: "),
            *self._loss_spans(health),
            TextSpan(text="."),
        ]
        return replace(
            measured, evidence=evidence, status="unsure", uncertainty="track lost", m=None
        )

    def no_box(self, where: str) -> Measurement:
        """Nothing to measure: SAM has no box on any frame, which its health calls lost."""
        evidence = [TextSpan(text=f"SAM has no box {where}.")]
        return self.judged(Measurement(None, "no box", evidence, []), None)

    def _fell(self, frame: int) -> bool:
        """The box's centre jumped mostly downward into `frame` (image y grows downward)."""
        before, after = self.boxes.get(frame - 1), self.boxes.get(frame)
        if before is None or after is None:
            return False
        (x0, y0), (x1, y1) = centre(before), centre(after)
        return y1 - y0 > abs(x1 - x0)

    def _without_falls(self, health: TrackHealth) -> TrackHealth:
        jumps = [f for f in health.centre_jumps if not self._fell(f)]
        lost = bool(health.area_jumps or jumps or health.missing_fraction > MISSING_FRACTION)
        return health.model_copy(update={"centre_jumps": jumps, "lost": lost})

    def _loss_spans(self, health: TrackHealth) -> list[TextSpan]:
        spans: list[TextSpan] = []
        for frames, what in ((health.area_jumps, "swelled"), (health.centre_jumps, "jumped")):
            if frames:
                spans += [
                    TextSpan(text=f"{'; ' if spans else ''}its box {what} at "),
                    *at_times([self.time(f) for f in frames]),
                ]
        if health.missing_fraction > MISSING_FRACTION:
            share = f"{health.missing_fraction:.0%}"
            spans.append(TextSpan(text=f"{'; ' if spans else ''}no box on {share} of frames"))
        return spans
