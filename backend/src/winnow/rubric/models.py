from typing import Literal, Self

from pydantic import BaseModel, Field, computed_field, model_validator

from winnow.criteria.english import english
from winnow.criteria.models import Criterion, RubricSettings, Status
from winnow.evaluation.stats import Proportion
from winnow.rubric.phrases import TextRange, uncovered_words
from winnow.triage.models import TriageDecision

DESCRIPTION_MAX = 2000  # characters


class Rubric(BaseModel):
    """A Description's Phrases, the Criteria each became, and what a grasp is."""

    description: str
    phrases: list[str]  # each an exact substring of the Description
    settings: RubricSettings
    criteria: list[Criterion]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        for phrase in self.phrases:
            if phrase not in self.description:
                raise ValueError(f"Phrase {phrase!r} isn't in the Description")
        for criterion in self.criteria:
            if criterion.phrase not in self.phrases:
                raise ValueError(f"Criterion {criterion.id} names an unknown Phrase")
        ids = [c.id for c in self.criteria]
        if len(set(ids)) != len(ids):
            raise ValueError("Criterion ids must be unique")
        return self


RubricOrigin = Literal["seed", "run"]


class RubricVersion(BaseModel):
    """A frozen Rubric: every Criterion result names the version it came from."""

    version: int
    created_at: str
    origin: RubricOrigin  # seed: the code's Rubric, replaced until one is Run; run: from Run
    rubric: Rubric


PhraseStatus = Literal["checked", "context", "unsupported"]


class DraftPhrase(BaseModel):
    """One Phrase of a draft's Description and what compile made of it. Its Criteria are the
    draft's Criteria whose `phrase` is its text."""

    text: str  # an exact substring of the Description
    start: int  # where it sits in the Description, in characters
    end: int
    restatement: str  # what it requires, said precisely
    status: PhraseStatus
    # Context: why it checks nothing, which the user can overrule. Unsupported: Spark's reason,
    # or the validation error that survived the repair turn.
    reason: str | None = None


class RejectedPhrase(BaseModel):
    """A Phrase Spark proposed that code refused, e.g. one that isn't in the Description."""

    text: str
    reason: str


class RubricDraft(BaseModel):
    """The Rubric being written on the Describe page: compiled from a Description, edited, and
    frozen into a Rubric version by Run."""

    description: str
    phrases: list[DraftPhrase]  # in Description order, never overlapping
    settings: RubricSettings
    criteria: list[Criterion]
    disabled: list[str] = []  # ids of Criteria switched off: shown, never scored or Run
    rejected: list[RejectedPhrase] = []
    # The changed text the last compile asked Spark about, keeping every other Phrase; None when
    # it compiled the whole Description.
    recompiled: list[TextRange] | None = None
    compiled_at: str

    def rubric(self) -> Rubric:
        """What Run freezes and the preview scores: every Phrase, the Criteria switched on."""
        return Rubric(
            description=self.description,
            phrases=[p.text for p in self.phrases],
            settings=self.settings,
            criteria=[c for c in self.criteria if c.id not in self.disabled],
        )

    @computed_field
    @property
    def uncovered(self) -> list[TextRange]:
        """Meaningful words outside every Phrase, so nothing written is silently ignored."""
        return uncovered_words(self.description, [(p.start, p.end) for p in self.phrases])

    @computed_field
    @property
    def english(self) -> dict[str, str]:
        """Each Criterion as the user reads it, by id."""
        return {c.id: english(c) for c in self.criteria}

    @computed_field
    @property
    def assumptions_unconfirmed(self) -> int:
        """Values guessed and not yet confirmed: a Rubric setting's, or a switched-on
        Criterion's. Run never waits for them."""
        settings = (self.settings.gripper_closed_level, self.settings.grasp_rise_m)
        guessed = sum(1 for s in settings if s.assumption is not None)
        return guessed + sum(len(c.assumptions) for c in self.rubric().criteria)


class CriterionEdit(BaseModel):
    """A direct edit on one Criterion card: no model call. Unset fields stay as they are."""

    threshold: float | None = None
    hard: bool | None = None
    enabled: bool | None = None


class DraftEdit(BaseModel):
    """Direct edits to the draft: Criterion cards by id, and the two Rubric settings. Setting a
    Rubric setting confirms it."""

    criteria: dict[str, CriterionEdit] = {}
    gripper_closed_level: float | None = Field(default=None, gt=0, lt=1)
    grasp_rise_m: float | None = Field(default=None, gt=0, le=0.5)


class AnchorValue(BaseModel):
    """One anchor Episode's result on one Criterion."""

    episode_id: str
    value: float | None  # None when it couldn't be measured
    status: Status


SanityWarning = Literal["too_rare", "too_common"]


class CriterionPreview(BaseModel):
    """How one Criterion sorts the anchor pool: its histogram's values and the counts, and for a
    hard Criterion in the Rubric the sanity monitor's reading of them (`rubric/sanity.py`)."""

    criterion_id: str
    english: str
    threshold: float
    margin: float  # the effective margin around the threshold, in `unit`
    unit: str
    passing: int
    failing: int
    unsure: int
    values: list[AnchorValue]
    # Sanity monitor: None and [] for a soft Criterion, or one switched off. The fail rate is
    # over every Episode of the pool; the warning fires below 2% (too_rare) or above 95%
    # (too_common). `only_rejects` are the Episodes Rejected only because of this Criterion.
    fail_rate: Proportion | None = None
    warning: SanityWarning | None = None
    only_rejects: list[str] = []


class AnchorEpisode(BaseModel):
    episode_id: str
    decision: TriageDecision
    confidence: float


class AnchorPreview(BaseModel):
    """A Rubric scored on the anchor pool's Episodes that have a Reference label (the rest stay
    blind), computed on every read: dragging a threshold re-sorts it with no model call."""

    rubric_version: int | None  # None: the draft, unfrozen
    keep: int
    reject: int
    needs_review: int
    episodes: list[AnchorEpisode]  # least confident first
    criteria: list[CriterionPreview]  # every Criterion, switched off or not
