"""The Review queue: what a reviewer is asked about each Needs review Episode."""

from pydantic import BaseModel


class UnsurePhrase(BaseModel):
    phrase: str
    signals: list[str]  # why it's unsure, e.g. "near threshold (4.4 cm against ≤ 5 cm)"


class ReviewItem(BaseModel):
    episode_id: str
    confidence: float
    reason: str
    unsure: list[UnsurePhrase]  # only the hard Phrases Winnow couldn't decide, in Rubric order


class ReviewQueue(BaseModel):
    rubric_version: int
    reviewed: int  # Episodes a review label took out of Needs review
    items: list[ReviewItem]  # strictly least confident first
