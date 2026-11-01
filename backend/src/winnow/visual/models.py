"""What Spark answered about one visual Criterion on one Episode, and the clip it watched."""

from typing import Literal

from pydantic import BaseModel, Field

from winnow.tracking.models import FrameBox

AnswerValue = Literal["pass", "fail", "unsure"]


class VisualReply(BaseModel):
    """One sample's structured answer: pass means the question's answer is yes."""

    answer: AnswerValue
    confidence: float = Field(ge=0, le=1)  # Spark's own, which only breaks ties
    observation: str  # what it saw, in one sentence


class VisualSample(BaseModel):
    prompt: str  # the frozen question or paraphrase this sample asked
    reply: VisualReply | None
    error: str | None  # why there's no reply


class VisualClip(BaseModel):
    """The short clip the crop step cut for one Criterion on one Episode."""

    name: str  # its file under the Episode's `visual/` folder, named by its spec's hash
    camera: str
    start: float  # s from the Episode's start
    end: float
    box: FrameBox | None  # the crop, in the camera's pixels; None for the whole view


class AskRequest(BaseModel):
    episode_ids: list[str] | None = None  # every ingested Episode when unset


class AskStarted(BaseModel):
    job_id: int | None  # None: the Rubric has no visual Criterion


class VisualAnswers(BaseModel):
    clip: VisualClip | None  # None when the crop step failed
    samples: list[VisualSample]  # one per frozen question and paraphrase
    error: str | None  # the crop or visual step's error, when it failed outright
