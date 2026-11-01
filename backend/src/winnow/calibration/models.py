"""Calibration: the margin multiplier s a Rubric version is scored with, tuned on the Dev set's
interview and review labels, and the thresholds those labels suggest."""

from pydantic import BaseModel

from winnow.rubric.models import RubricVersion


class CalibrationRecord(BaseModel):
    """One run of the scan on a Rubric version; the latest is the s it is scored with."""

    rubric_version: int
    s: float
    n_labels: int  # labelled (Episode, Phrase) pairs it was tuned on
    errors: int  # of those, crisp Phrase results their label contradicts at s
    bound_met: bool  # False: no s met the bound, so s is the widest on the grid
    unstable: bool  # dropping some 2 labels moves s: "margins unstable: label more"
    created_at: str


class ThresholdSuggestion(BaseModel):
    """Where labels put a Criterion's threshold, when two or more contradict its crisp result:
    midway between the closest labelled pass and fail values, their gap as its margin. Only
    accepting it, as a new Rubric version, moves the threshold."""

    criterion_id: str
    phrase: str
    english: str  # the Criterion as it reads now
    suggested_english: str  # as it would read with the suggested threshold
    threshold: float
    unit: str
    suggested_threshold: float
    suggested_margin: float
    contradicting: int  # labels its crisp result contradicts
    labelled: int  # labelled anchor Episodes it has a value on


class Calibration(BaseModel):
    """The latest Rubric version's s and the thresholds labels suggest for it now."""

    rubric_version: int
    s: float  # what it is scored with: the latest record's, or 1 when it has none
    record: CalibrationRecord | None  # None: never calibrated, so s is 1
    labelled: int  # labelled (Episode, Phrase) pairs on the anchor pool now
    grid: list[float]  # the s values scanned, widest first
    max_error_rate: float  # the bound the scan keeps: errors' upper bound at most this
    confidence: float  # of that one-sided upper bound
    suggestions: list[ThresholdSuggestion]


class AcceptedSuggestion(BaseModel):
    """The Rubric version accepting a suggestion froze, and what became of the draft."""

    version: RubricVersion  # keeps the s its suggestion was made at
    draft_updated: bool  # False: no draft, or its Criterion now checks something else
    draft_note: str  # what happened to the draft, to show
