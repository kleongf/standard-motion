"""What the scoring function says about one Episode, and what the Episodes table lists."""

from typing import Literal

from pydantic import BaseModel

from winnow.criteria.models import (
    Comparator,
    Moment,
    Status,
    TextSpan,
    TrackPlot,
    UncertaintySignal,
)
from winnow.criteria.primitives import Kind, Primitive
from winnow.visual.models import VisualAnswers

TriageDecision = Literal["keep", "reject", "needs_review"]
ReasonSource = Literal["template", "spark"]
LabelSource = Literal["interview", "review", "audit"]


class Label(BaseModel):
    """A human's answer for one Phrase of one Episode; it overrides that Phrase's result."""

    phrase: str
    value: Literal["pass", "fail"]
    source: LabelSource


class TimeWindow(BaseModel):
    start: float  # s
    end: float  # s


class CriterionResult(BaseModel):
    criterion_id: str
    phrase: str
    primitive: Primitive
    kind: Kind
    hard: bool
    english: str
    status: Status
    value: float | None
    measurement: str  # the value as the user reads it, e.g. "3 attempts"
    comparator: Comparator
    threshold: float
    unit: str
    evidence: list[TextSpan]
    moments: list[Moment]
    window: TimeWindow | None  # None when the window is empty
    window_name: str
    at_s: float | None  # where it went wrong, for a fail
    uncertainty: UncertaintySignal | None
    margin: float  # the effective margin around the threshold, in `unit`
    p_pass: float  # how likely this Criterion passes, 0 to 1
    camera: str | None  # the view to show; None for robot data
    track_plot: TrackPlot | None  # tracked Criteria: the signal they are decided on
    visual: VisualAnswers | None = None  # a visual Criterion's samples and clip


class PhraseResult(BaseModel):
    phrase: str
    hard: bool  # has a hard Criterion, so it counts toward the Triage decision
    status: Status | None  # None: no Criterion checks it
    label: Label | None  # the human answer that set `status`, if any
    p_pass: float | None  # the min over its deciding Criteria (1 or 0 when labelled)


class Triage(BaseModel):
    decision: TriageDecision
    reason: list[TextSpan]  # one sentence; spans with a time seek to it
    criteria: list[CriterionResult]
    phrases: list[PhraseResult]
    p_keep: float  # the min over hard Phrases' p_pass
    confidence: float  # max(p_keep, 1 - p_keep): 0.5 is a coin toss
    reason_source: ReasonSource = "template"  # "spark": Spark's Reason, swapped in for its key


class EpisodeTriage(Triage):
    episode_id: str
    rubric_version: int
    # The mean robust z of its soft Criteria within the run (`triage.quality`): higher is better.
    # None with no soft value to compare, and for an Episode scored on its own.
    quality: float | None = None


class PhraseChip(BaseModel):
    phrase: str
    status: Literal["fail", "unsure"]


class TriageRow(BaseModel):
    episode_id: str
    decision: TriageDecision
    reason: str
    confidence: float
    not_passed: list[PhraseChip]  # checked Phrases that didn't pass, in Rubric order
    uncertainty: list[UncertaintySignal]  # every signal on the Episode's results, once each
    quality: float | None  # relative to the run, from soft Criteria only; never decides


class TriageList(BaseModel):
    rubric_version: int
    rows: list[TriageRow]


class ReasonsStarted(BaseModel):
    job_id: int | None  # None: every Reject and Needs review already has Spark's Reason
