"""Reference labels: a human's blind judgment of an Episode against the frozen Description, per
Phrase, used only to score Winnow and the baselines. Scoring never reads them."""

from typing import Self

from pydantic import BaseModel, Field, model_validator


class FrozenDescription(BaseModel):
    """The Description Reference labels are given against, and its Phrases in order."""

    text: str
    phrases: list[str]


class FailInterval(BaseModel):
    """Where in the Episode a Phrase fails, in seconds from its start."""

    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end_s < self.start_s:
            raise ValueError("An interval must end at or after its start")
        return self


class PhraseLabel(BaseModel):
    phrase: str
    passed: bool
    interval: FailInterval | None = None  # required for a fail, absent for a pass

    @model_validator(mode="after")
    def _interval_marks_a_fail(self) -> Self:
        if self.passed != (self.interval is None):
            raise ValueError("A failed Phrase needs an interval, and only a failed one has one")
        return self


class ReferenceLabelDraw(BaseModel):
    """What the labeller submits for one Episode."""

    phrases: list[PhraseLabel]
    instruction: str | None = None  # written by the labeller where the Episode has none
    elapsed_s: float = Field(ge=0)  # time spent labelling, for review minutes saved
    relabel: bool = False  # the second, blind pass that measures the labeller's own slack


class ReferenceLabel(BaseModel):
    episode_id: str
    relabel: bool
    description: str  # the Description text it was given against
    phrases: list[PhraseLabel]
    instruction: str | None
    elapsed_s: float
    labelled_at: str
