from typing import Literal

from pydantic import AliasChoices, BaseModel, Field

# What an export writes: the Keeps only (the default), or the Needs review Episodes with them.
Include = Literal["keep", "keep_and_review"]
Exported = Literal["keep", "needs_review"]  # the Triage decisions an export can write


class Rejection(BaseModel):
    """A line of an export's rejections.jsonl: an Episode left out, and why."""

    episode_id: str
    source_index: int
    decision: Literal["reject", "needs_review"]
    reason: str


class ManifestEpisode(BaseModel):
    """An exported Episode in manifest.json: where it went in the export, where it came from,
    and its Triage decision."""

    exported_episode_index: int  # within its source's exported dataset
    source: str
    source_episode_index: int
    episode_id: str
    decision: Exported


class Skipped(BaseModel):
    """How many Episodes an export left out, by cause."""

    reject: int
    needs_review: int
    test_set: int


class Manifest(BaseModel):
    """manifest.json, at an export's root: what it holds and what it was decided with."""

    created_at: str  # ISO 8601, UTC
    include: Include = "keep"  # exports from before the choice wrote Keeps only
    rubric_version: int
    margin_multiplier: float  # s, the latest Rubric version's
    not_reference_labelled: int  # of the Episodes decided, those without a Reference label
    # Read as `kept` from manifests written before Needs review could be exported.
    exported: list[ManifestEpisode] = Field(validation_alias=AliasChoices("exported", "kept"))
    skipped: Skipped


class ExportRequest(BaseModel):
    include: Include = "keep"


class ExportStarted(BaseModel):
    job_id: int


class DecisionCounts(BaseModel):
    """Episodes as an export sees them. Decisions are counted only for the Reference-labelled:
    the rest's stay hidden until they're labelled, or exported."""

    keep: int
    needs_review: int
    reject: int
    awaiting_label: int  # outside the Test set with no Reference label: exported by decision
    test_set: int  # never exported


class SourceCounts(DecisionCounts):
    source: str


class ExportPreview(BaseModel):
    """What an export would hold, before it runs, per source; `exported` is how many of the
    Reference-labelled it writes with `include`, and `nothing_exported` why it would write none
    (None while Episodes awaiting a label could still be)."""

    include: Include
    rubric_version: int
    sources: list[SourceCounts]
    exported: int
    nothing_exported: str | None


class PastExport(BaseModel):
    """An export written under the data dir's exports/, from its manifest.json."""

    path: str
    created_at: str
    episodes: int
    include: Include
