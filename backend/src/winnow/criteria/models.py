"""The Criterion schema and the Rubric-level settings every grasp-based Criterion shares.

A Criterion is a typed call to one catalog primitive with one comparator; the English the user
reads is rendered from these fields (`criteria.english`), so the Rubric and the code can't drift.
"""

from typing import Literal, Self

from pydantic import BaseModel, Field, computed_field, model_validator

from winnow.criteria.primitives import PARAPHRASES, PRIMITIVES, Kind, Primitive

Comparator = Literal["<", "<=", ">=", ">", "=="]
WindowKind = Literal["whole", "before_grasp", "holding", "after_release", "last_n_s"]
# What a visual Criterion's clip shows: the whole view, or the object's final box joined with the
# target box, enlarged.
CropKind = Literal["view", "placement"]
Status = Literal["pass", "fail", "unsure"]
# Why a result is unsure (or, for "unconfirmed fail", why its fail can't reject on its own).
UncertaintySignal = Literal[
    "near threshold",
    "near threshold (count)",
    "samples split",
    "Spark said unsure",
    "unconfirmed fail",
    "window empty",
    "source missing",
    "step failed",
    "track lost",
]


class Window(BaseModel):
    """The stretch of the Episode a Criterion looks at. Grasp-relative windows are empty in an
    Episode with no grasp (and `after_release` when the grasp never opens)."""

    kind: WindowKind = "whole"
    seconds: float | None = Field(default=None, gt=0)  # last_n_s only

    @model_validator(mode="after")
    def _seconds_only_for_last_n_s(self) -> Self:
        if (self.kind == "last_n_s") != (self.seconds is not None):
            raise ValueError("`seconds` is required for last_n_s and only for it")
        return self


class Criterion(BaseModel):
    id: str  # stable slug: kept while its Phrase and primitive are unchanged
    phrase: str  # an exact substring of the Description
    primitive: Primitive
    params: dict[str, float] = {}  # typed per primitive by the catalog
    comparator: Comparator
    threshold: float
    unit: str
    margin: float = Field(default=0.0, ge=0)
    window: Window = Window()
    views: list[str] = []  # cameras, for tracked and visual Criteria
    question: str | None = None  # visual Criteria: frozen at compile
    paraphrases: list[str] = []
    crop: CropKind | None = None  # visual Criteria: None means the whole view
    hard: bool = True
    assumptions: list[str] = []  # values Spark (or the seed) had to guess

    @model_validator(mode="after")
    def _params_match_the_primitive(self) -> Self:
        expected = set(PRIMITIVES[self.primitive].params)
        if set(self.params) != expected:
            raise ValueError(f"{self.primitive} takes params {sorted(expected)}")
        return self

    @model_validator(mode="after")
    def _visual_criteria_ask_a_frozen_question(self) -> Self:
        if self.kind == "visual" and not (self.question and len(self.paraphrases) == PARAPHRASES):
            raise ValueError(f"a visual Criterion needs a question and {PARAPHRASES} paraphrases")
        return self

    @computed_field
    @property
    def kind(self) -> Kind:
        return PRIMITIVES[self.primitive].kind


class Setting(BaseModel):
    value: float
    margin: float = Field(ge=0)
    assumption: str | None = None  # set while the value is a guess nobody confirmed


class RubricSettings(BaseModel):
    """What a grasp is, shared by `grasp_attempts` and every grasp-relative window."""

    gripper_closed_level: Setting  # gripper state (0 open, 1 closed) above which it is closed
    grasp_rise_m: Setting  # the grasp is the last closure during which the arm rises this much


class Moment(BaseModel):
    """A point in time that matters to a Criterion result."""

    t: float  # s from the Episode's start
    label: str


class PlotPoint(BaseModel):
    t: float  # s from the Episode's start
    value: float | None  # None where SAM had no box


class TrackPlot(BaseModel):
    """The signal a tracked Criterion is decided on, per 5 fps frame of the stretch it reads."""

    label: str  # e.g. "Object from the fingers"
    unit: str  # e.g. "box-widths"
    level: float  # the line the signal is judged against
    points: list[PlotPoint]


class TextSpan(BaseModel):
    """A piece of Evidence or Reason text; a span with `t` seeks the playhead there."""

    text: str
    t: float | None = None
