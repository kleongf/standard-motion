"""One labelled Episode as the report sees it: its Reference label's failing Phrases and their
intervals, and what each system decided, what its Reason claims went wrong, and how sure it was.
This is the narrow seam between scoring and the report: only these cross it, so new Criteria and
signals leave the report alone."""

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from winnow.baseline.models import BaselineAnswer, EpisodeBaseline
from winnow.baseline.prompts import FROZEN, Description
from winnow.reference_labels.models import FailInterval, ReferenceLabel
from winnow.tracking.models import TrackKind
from winnow.triage.models import Triage, TriageDecision
from winnow.triage.reason import labelled_fails, rejecting_fails

SparkDecision = Literal["keep", "reject"]


@dataclass(frozen=True)
class Claim:
    """What a Reject's Reason says went wrong: the Phrase it names and when, if it says."""

    phrase: str | None
    at_s: float | None


@dataclass(frozen=True)
class Ranking:
    """Where an Episode sits on a system's risk–coverage curve: the side it leans to, even when it
    abstains, and how sure it is (0.5 to 1). `tiebreak` orders equal confidences."""

    lean: SparkDecision
    confidence: float
    tiebreak: float = 0.0


@dataclass(frozen=True)
class TrackCheck:
    """One SAM track of an Episode, as tracking health counts it."""

    lost: bool  # its health over the whole track flags it lost
    review_signal: bool  # a hard Criterion reading it is unsure for "track lost"


@dataclass(frozen=True)
class EvaluationCase:
    episode_id: str
    duration_s: float
    failed: Mapping[str, FailInterval]  # each Phrase its Reference label fails, and where
    winnow: TriageDecision
    spark_alone: SparkDecision | None  # the majority of its samples; None without one
    winnow_claim: Claim | None  # for a Reject: its Reason's leading fail
    spark_alone_claim: Claim | None  # for a Reject: its samples' failure type and time
    winnow_ranking: Ranking
    spark_alone_ranking: Ranking
    dataset_outcome: bool | None = None  # the source's success flag, if it ships one
    failbench: bool | None = None  # Spark's "did it succeed?" answer; None without one
    elapsed_s: float = 0.0  # the label-mode timer on its first-pass Reference label
    tracks: Mapping[TrackKind, TrackCheck] = field(default_factory=dict[TrackKind, TrackCheck])
    too_small: bool = False  # excluded at selection as "object too small to see"

    @property
    def description_failure(self) -> bool:
        """Its Reference label fails at least one Phrase."""
        return bool(self.failed)


def failed_phrases(label: ReferenceLabel) -> dict[str, FailInterval]:
    return {p.phrase: p.interval for p in label.phrases if p.interval is not None}


def _span(text: str, part: str) -> range:
    start = text.find(part)
    return range(start, start + len(part)) if start >= 0 else range(0)


def frozen_phrase(phrase: str, description: Description = FROZEN) -> str | None:
    """The frozen Phrase a Rubric Phrase overlaps most in the Description, since a compiled Rubric
    may split it differently from the Phrases Reference labels are given per; None when it
    overlaps none."""
    claimed = _span(description.text, phrase)

    def overlap(frozen: str) -> int:
        span = _span(description.text, frozen)
        return max(0, min(span.stop, claimed.stop) - max(span.start, claimed.start))

    best = max(description.phrases, key=overlap)
    return best if claimed and overlap(best) > 0 else None


def winnow_claim(triage: Triage) -> Claim | None:
    """A Reject's Reason leads with its earliest conclusive fail; a label-only Reject names the
    labelled Phrase but no time. The Phrase is read as the frozen Phrase it overlaps."""
    if triage.decision != "reject":
        return None
    fails = rejecting_fails(triage.criteria, triage.phrases)
    if fails:
        return Claim(frozen_phrase(fails[0].phrase), fails[0].at_s)
    labelled = labelled_fails(triage.phrases)
    return Claim(frozen_phrase(labelled[0].phrase) if labelled else None, None)


def winnow_ranking(triage: Triage) -> Ranking:
    """Needs review leans to the side P_keep favours; a coin toss leans to Reject, the side that
    costs a dataset less."""
    if triage.decision != "needs_review":
        return Ranking(triage.decision, triage.confidence)
    return Ranking("keep" if triage.p_keep > 0.5 else "reject", triage.confidence)


def _answers(baseline: EpisodeBaseline) -> list[BaselineAnswer]:
    return [s.answer for s in baseline.samples if s.answer is not None]


def spark_alone_decision(baseline: EpisodeBaseline) -> SparkDecision | None:
    """The majority over answered samples; a tie or no answer at all decides nothing."""
    decisions: Sequence[SparkDecision] = [a.decision for a in _answers(baseline)]
    keeps = decisions.count("keep")
    rejects = len(decisions) - keeps
    if keeps == rejects:
        return None
    return "keep" if keeps > rejects else "reject"


def _stated(answers: Sequence[BaselineAnswer], side: SparkDecision) -> float:
    """The mean stated confidence of the samples on one side; 0 with none."""
    on_side = [a.confidence for a in answers if a.decision == side]
    return statistics.fmean(on_side) if on_side else 0.0


def spark_alone_ranking(baseline: EpisodeBaseline) -> Ranking:
    """The same agreement score as Winnow's visual Criteria: P_keep = (keeps + 1) / (K + 2) over
    K answered samples, ties broken by stated confidence. With no majority it leans to the side
    stated more confidently, and to Reject when even that ties."""
    answers = _answers(baseline)
    keeps = sum(a.decision == "keep" for a in answers)
    p_keep = (keeps + 1) / (len(answers) + 2)
    lean = spark_alone_decision(baseline)
    if lean is None:
        lean = "keep" if _stated(answers, "keep") > _stated(answers, "reject") else "reject"
    return Ranking(lean, max(p_keep, 1 - p_keep), tiebreak=_stated(answers, lean))


def spark_alone_claim(baseline: EpisodeBaseline) -> Claim | None:
    """For a majority Reject: the failure type most of its rejecting samples name (the earliest
    named on a tie), at the median of the times they give for it."""
    if spark_alone_decision(baseline) != "reject":
        return None
    rejecting = [a for a in _answers(baseline) if a.decision == "reject"]
    named = [a.failure_type for a in rejecting]
    phrase = max(dict.fromkeys(named), key=named.count)
    times = [a.time_s for a in rejecting if a.failure_type == phrase and a.time_s is not None]
    return Claim(phrase, statistics.median(times) if times else None)
