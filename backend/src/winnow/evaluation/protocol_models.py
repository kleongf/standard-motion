"""The report's protocol sections beyond the comparison: what each Meta model adds (the source
ablation), how often SAM lost the object, what a run costs in Meta calls and in a person's
minutes, the Dataset outcome against Reference labels, and the FailBench check."""

from typing import Literal

from pydantic import BaseModel

from winnow.evaluation.stats import Proportion
from winnow.sets.models import SetName
from winnow.tracking.models import TrackKind
from winnow.triage.models import TriageDecision

SourceMask = Literal["robot_data", "robot_data_sam", "robot_data_visual", "all"]


class AblationRow(BaseModel):
    """Winnow re-scored from what is already stored with only some sources' Criteria: a masked
    source's Criteria are left out, as if the Rubric had been compiled without that model, so a
    Phrase only they checked goes unchecked. No Meta call is made."""

    mask: SourceMask
    label: str
    criteria: int  # the Rubric's Criteria this row keeps
    of: int  # all the Rubric's Criteria
    false_keeps: Proportion  # description failures kept, of all description failures
    # Correct Rejects whose Reason is right at the measured slack; None without a slack
    right_reason: Proportion | None
    coverage: Proportion  # Episodes decided automatically, of all labelled Episodes


class TrackHealthRow(BaseModel):
    """One SAM track type over the labelled Episodes."""

    kind: TrackKind
    label: str
    lost: Proportion  # Episodes whose track is flagged lost, of those with a track
    # Needs review decisions where a hard Criterion reading this track is unsure for "track lost"
    needs_review: int
    # Of the lost tracks, those on Episodes excluded at selection as "object too small to see"
    too_small: int


class StepCost(BaseModel):
    """What one pipeline step spent on the set's Episodes, from the cost log."""

    step: str  # the cost log's purpose prefix, e.g. "track_wrist"
    label: str
    system: Literal["winnow", "spark_alone", "other"]
    calls: int  # paid calls; cache hits cost nothing and aren't counted
    episodes: int  # the set's Episodes it spent anything on
    usd: float


class MetaCost(BaseModel):
    """Cost per 1,000 Episodes, extrapolated from what the set's Episodes cost in the cost log:
    x10 for a Test set of 100. Not run at 1,000."""

    episodes: int  # in the set: the extrapolation is per Episode of these
    winnow_usd: float
    winnow_per_1000_usd: float | None  # None for an empty set
    spark_alone_usd: float  # its three samples and the FailBench check
    spark_alone_per_1000_usd: float | None
    compile_usd: float  # every Rubric compile so far: once per Project, not per Episode
    steps: list[StepCost]


class ReviewTime(BaseModel):
    """A person's minutes, from the label-mode timer: what Winnow saves by deciding Episodes
    automatically, and the human cost per Episode left (one hand-drawn box plus Needs review)."""

    timed: int  # labelled Episodes, each timed while it was labelled
    minutes_per_episode: float | None  # the timer's mean; None with nothing timed
    decided: int  # Episodes Winnow decided automatically
    minutes_saved: float | None  # minutes_per_episode x decided
    needs_review: Proportion  # Episodes routed to a person, of the labelled
    # Per Episode: the Needs review share x minutes_per_episode. The timer includes drawing the
    # box, which isn't timed on its own.
    needs_review_minutes_per_episode: float | None


class OutcomeDisagreement(BaseModel):
    episode_id: str
    dataset_outcome: bool  # the source's success flag
    failed_phrases: list[str]  # the Phrases its Reference label fails; empty: meets the Description


class DatasetOutcome(BaseModel):
    """The Dataset outcome ("was the task done") against the Reference label ("does it meet the
    Description"), over the labelled Episodes whose source ships one."""

    compared: int
    no_outcome: int  # labelled Episodes whose source has no success flag
    success_meets: int
    success_fails: int  # a success the Description rejects, as droid_100 Episode 42
    failure_meets: int
    failure_fails: int
    disagreements: list[OutcomeDisagreement]


class FailBenchCheck(BaseModel):
    """Spark's plain "did it succeed?" answer scored against the Dataset outcome, to tie back to
    FailBench's published 0.72 balanced accuracy on DROID."""

    answered: int  # labelled Episodes with both an answer and a Dataset outcome
    agrees: Proportion  # its answer matches the Dataset outcome
    failures_caught: Proportion  # said it failed, of the Dataset's failures
    balanced_accuracy: float | None  # None unless both outcomes occur


class Disagreement(BaseModel):
    """A Reference-labelled Episode where Winnow's Triage decision (as the Workstation shows it
    now) and Spark alone's majority answer differ."""

    episode_id: str
    set_name: SetName | None
    winnow: TriageDecision
    winnow_reason: str
    spark_alone: Literal["keep", "reject"] | None  # None: its samples split evenly
    spark_alone_reason: str | None  # a sample on its majority side
    failed_phrases: list[str]  # the Phrases its Reference label fails; empty: meets it
