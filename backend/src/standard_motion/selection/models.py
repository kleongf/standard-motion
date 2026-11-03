"""The droid_1.0.1 selection pass: pick-and-place Episodes chosen by task type only (#10).

A fixed-seed sample, a contact sheet each, Spark's "pick-and-place? object? target?", and a
human confirm or exclude. The Dataset outcome is never shown here, so it can't steer the pick.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

ExclusionReason = Literal["not pick-and-place", "object too small to see"]
CandidateStatus = Literal["pending", "confirmed", "excluded"]


class SelectionAnswer(BaseModel):
    """Spark's reading of one contact sheet."""

    pick_and_place: bool
    object: str | None
    target: str | None


class Candidate(BaseModel):
    episode_id: str
    source: str
    index: int
    seed: int
    task: str | None  # the Episode's recorded instruction, if any
    pick_and_place: bool | None  # None when Spark's call failed
    object: str | None
    target: str | None
    error: str | None
    status: CandidateStatus
    exclusion_reason: ExclusionReason | None
    ingested: bool


class Confirm(BaseModel):
    decision: Literal["confirm"]


class Exclude(BaseModel):
    decision: Literal["exclude"]
    reason: ExclusionReason


Decision = Annotated[Confirm | Exclude, Field(discriminator="decision")]
