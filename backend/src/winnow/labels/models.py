"""Labels: a human's pass or fail on one Phrase of one Episode, from the interview, Review or the
Audit tab. Unlike Reference labels, scoring reads interview and review labels: each overrides its
Phrase's result, until it is withdrawn (an interview answer undone). Audit labels only measure
Keep precision; scoring never reads them."""

from typing import Literal

from pydantic import BaseModel

from winnow.triage.models import Label, LabelSource


class LabelDraw(BaseModel):
    """What a reviewer (or the interview) submits for one Phrase of one Episode."""

    phrase: str
    value: Literal["pass", "fail"]
    source: LabelSource


class StoredLabel(Label):
    """A label as kept: labels hang off the Phrase, so one whose Phrase text changed stays in
    history but no longer applies."""

    episode_id: str
    rubric_version: int | None  # the version it was given against; None: the Rubric draft
    labelled_at: str
    id: int | None = None  # set once stored
    withdrawn_at: str | None = None  # undone (an interview answer's): kept, never applied
