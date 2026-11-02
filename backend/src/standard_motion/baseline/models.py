"""Spark alone's answers, kept for the `evaluation` module; no page shows them."""

from typing import Literal

from pydantic import BaseModel, Field


class BaselineAnswer(BaseModel):
    decision: Literal["keep", "reject"]
    failure_type: str | None  # a Phrase of the Description, or "other"
    time_s: float | None
    reason: str
    confidence: float = Field(ge=0, le=1)


class FailBenchAnswer(BaseModel):
    success: bool
    confidence: float = Field(ge=0, le=1)


class SampleResult(BaseModel):
    sample: int
    answer: BaselineAnswer | None
    error: str | None  # why there's no answer


class FailBenchResult(BaseModel):
    answer: FailBenchAnswer | None
    error: str | None


class EpisodeBaseline(BaseModel):
    samples: list[SampleResult]
    failbench: FailBenchResult | None
