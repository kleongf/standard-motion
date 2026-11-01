"""The Dev set and the Test set: explicit Episode lists, frozen once chosen so that reported
numbers never come from Episodes the Rubric was tuned on."""

from typing import Literal

from pydantic import BaseModel, Field

SetName = Literal["dev", "test"]
SET_NAMES: tuple[SetName, ...] = ("dev", "test")
SET_LABELS: dict[SetName, str] = {"dev": "Dev set", "test": "Test set"}


class EpisodeSet(BaseModel):
    name: SetName
    size: int
    frozen_at: str | None  # when membership became immutable; None while it can still change
    episode_ids: list[str]


class SetMembers(BaseModel):
    episode_ids: list[str] = Field(min_length=1)


class FreezeRequest(BaseModel):
    force: bool = False  # freeze although it breaks the protocol


class FreezeWarnings(BaseModel):
    """The 409 body when a freeze would break the protocol and wasn't forced."""

    detail: str
    warnings: list[str]
