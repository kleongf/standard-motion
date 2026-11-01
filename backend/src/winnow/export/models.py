from typing import Literal

from pydantic import BaseModel


class Rejection(BaseModel):
    """A line of an export's rejections.jsonl: an Episode left out, and why."""

    episode_id: str
    source_index: int
    decision: Literal["reject", "needs_review"]
    reason: str


class ManifestEpisode(BaseModel):
    """A kept Episode in manifest.json: where it went in the export, and where it came from."""

    exported_episode_index: int  # within its source's exported dataset
    source: str
    source_episode_index: int
    episode_id: str
    decision: Literal["keep"]


class Skipped(BaseModel):
    """How many Episodes an export left out, by cause."""

    reject: int
    needs_review: int
    test_set: int


class Manifest(BaseModel):
    """manifest.json, at an export's root: what it holds and what it was decided with."""

    created_at: str  # ISO 8601, UTC
    rubric_version: int
    margin_multiplier: float  # s, the latest Rubric version's
    not_reference_labelled: int  # of the Episodes decided, those without a Reference label
    kept: list[ManifestEpisode]
    skipped: Skipped


class ExportStarted(BaseModel):
    job_id: int


class ExportScope(BaseModel):
    """What an export would decide on, before it runs: every Episode outside the Test set, and
    how many of them have no Reference label yet, whose decisions exporting shows."""

    episodes: int
    unlabelled: int
