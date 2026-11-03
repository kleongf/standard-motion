"""Background work: a job is a list of idempotent work items, each with its own status."""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

Status = Literal["queued", "running", "done", "failed"]

# Runs one work item; returns an optional note for its status (e.g. "already ingested").
Step = Callable[[Mapping[str, object]], Awaitable[str | None]]


@dataclass(frozen=True)
class WorkItem:
    step: str
    args: Mapping[str, object]  # JSON-serializable
    label: str  # what the item is about, e.g. "droid_100:42"
    after: int | None = None  # position of an item in the same job that must succeed first


class JobItem(BaseModel):
    position: int
    step: str
    label: str
    status: Status
    detail: str | None


class Job(BaseModel):
    id: int
    kind: str
    created_at: str
    total: int
    queued: int
    running: int
    done: int
    failed: int
    finished: bool
    items: list[JobItem]
