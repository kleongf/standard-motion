"""SAM tracking health per track type: how often the track is flagged lost, the Needs review
decisions a lost track left behind, and how many lost tracks were on Episodes whose object the
selection pass already called too small to see."""

from collections.abc import Sequence

from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.primitives import PRIMITIVES, Source
from winnow.evaluation.cases import EvaluationCase, TrackCheck
from winnow.evaluation.protocol_models import TrackHealthRow
from winnow.evaluation.stats import wilson
from winnow.tracking.models import TrackKind
from winnow.triage.models import Triage

TRACKS: dict[TrackKind, tuple[str, Source]] = {
    "wrist": ("Wrist object track", "wrist track"),
    "exterior": ("Exterior object track", "exterior track"),
}


def track_checks(facts: EpisodeFacts, triage: Triage) -> dict[TrackKind, TrackCheck]:
    """Each track the Episode was scored with, and whether it was lost and made a hard
    Criterion unsure. A gripper that never closed leaves no wrist track to judge."""
    checks: dict[TrackKind, TrackCheck] = {}
    for kind, (_, source) in TRACKS.items():
        track = facts.track_for(source)
        if track is None or track.health is None:
            continue
        signal = any(
            r.hard and r.uncertainty == "track lost" and PRIMITIVES[r.primitive].source == source
            for r in triage.criteria
        )
        checks[kind] = TrackCheck(lost=track.health.lost, review_signal=signal)
    return checks


def health_row(kind: TrackKind, cases: Sequence[EvaluationCase]) -> TrackHealthRow:
    tracked = [(c, c.tracks[kind]) for c in cases if kind in c.tracks]
    lost = [c for c, check in tracked if check.lost]
    return TrackHealthRow(
        kind=kind,
        label=TRACKS[kind][0],
        lost=wilson(len(lost), len(tracked)),
        needs_review=sum(
            c.winnow == "needs_review" and check.review_signal for c, check in tracked
        ),
        too_small=sum(c.too_small for c in lost),
    )


def tracking_health(cases: Sequence[EvaluationCase]) -> list[TrackHealthRow]:
    return [health_row(kind, cases) for kind in TRACKS]
