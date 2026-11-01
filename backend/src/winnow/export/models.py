from typing import Literal

from pydantic import BaseModel


class Rejection(BaseModel):
    """A line of an export's rejections.jsonl: an Episode left out, and why."""

    episode_id: str
    source_index: int
    decision: Literal["reject", "needs_review"]
    reason: str


class ExportStarted(BaseModel):
    job_id: int


class ExportScope(BaseModel):
    """What an export would decide on, before it runs: every Episode outside the Test set, and
    how many of them have no Reference label yet, whose decisions exporting shows."""

    episodes: int
    unlabelled: int
