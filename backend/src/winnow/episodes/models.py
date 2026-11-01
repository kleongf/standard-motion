from dataclasses import dataclass
from typing import Annotated, Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, Field

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class EpisodeSignals:
    """An Episode's robot data, one row per frame."""

    episode_index: int
    fps: float
    timestamps: FloatArray
    position: FloatArray  # end-effector xyz in metres, shape (n, 3)
    gripper: FloatArray  # 0 = open, 1 = closed
    dataset_outcome: bool | None  # the success flag the source shipped with, if any
    joint_positions: FloatArray | None = None  # shape (n, 7); droid_1.0.1 only
    camera_extrinsics: dict[str, FloatArray] | None = None  # per camera, shape (n, 6)

    @property
    def duration_s(self) -> float:
        return float(self.timestamps[-1] - self.timestamps[0]) if len(self.timestamps) else 0.0


@dataclass(frozen=True)
class SourceEpisode:
    """What a source adapter yields for one Episode, before ingest."""

    signals: EpisodeSignals
    instruction: str | None  # the Episode's own task text; None where the source dropped it


class Episode(BaseModel):
    """An ingested Episode, as the app lists it."""

    id: str  # "<source>:<index>", e.g. "droid_100:42"
    source: str
    index: int
    instruction: str | None
    dataset_outcome: bool | None  # None in the API until the Episode has a Reference label
    # Has a first-pass Reference label, so its outputs show; set by the blind gate.
    reference_labelled: bool = False
    frames: int
    fps: float
    duration_s: float
    cameras: list[str]  # cameras with a clip to play
    task_object: str | None  # the object moved, from the droid_1.0.1 selection pass
    task_target: str | None  # where it goes; prompts SAM for the target box


class Signals(BaseModel):
    """Per-frame robot data for the Workstation's plots, on a time axis starting at 0."""

    t: list[float]  # s
    gripper: list[float]  # 0 open, 1 closed
    z: list[float]  # end-effector height, m
    speed: list[float]  # end-effector speed, m/s, smoothed


class IngestRequest(BaseModel):
    source: Literal["droid_100", "droid_1.0.1"]
    indices: list[Annotated[int, Field(ge=0)]] = Field(min_length=1)


class IngestStarted(BaseModel):
    job_id: int
