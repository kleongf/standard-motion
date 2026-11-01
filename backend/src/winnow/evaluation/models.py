"""The evaluation report: Winnow and the baselines scored against Reference labels.

Each metric family is one section of `EvaluationReport`; later sections (right reason,
risk–coverage, the source ablation, cost) join as fields beside `comparison`.
"""

from typing import Literal

from pydantic import BaseModel, Field

from winnow.evaluation.protocol_models import (
    AblationRow,
    DatasetOutcome,
    FailBenchCheck,
    MetaCost,
    ReviewTime,
    TrackHealthRow,
)
from winnow.evaluation.stats import Proportion
from winnow.sets.models import SetName

System = Literal["winnow", "winnow_review_kept", "spark_alone", "length_alone"]
SYSTEM_LABELS: dict[System, str] = {
    "winnow": "Winnow",
    "winnow_review_kept": "Winnow (all Needs review kept)",
    "spark_alone": "Spark alone",
    "length_alone": "Length alone",
}


class SystemRow(BaseModel):
    system: System
    label: str
    keeps: int
    rejects: int
    undecided: int  # Winnow's Needs review; Spark alone with no majority answer
    false_keeps: Proportion  # description failures kept, of all description failures
    false_rejects: Proportion  # Episodes meeting the Description rejected, of all of them
    coverage: Proportion  # Episodes decided automatically, of all labelled Episodes
    # The mean of failures rejected and Episodes meeting the Description kept, over the Episodes
    # it decided; None unless it decided some of each.
    balanced_accuracy: float | None


class LengthRule(BaseModel):
    """Length alone's one duration threshold, chosen in hindsight on the evaluated set."""

    keep: Literal["longer", "shorter"]  # keep Episodes at least / at most `threshold_s` long
    threshold_s: float


class Comparison(BaseModel):
    rows: list[SystemRow]
    length_rule: LengthRule | None  # None when no Episode is labelled


class PhraseFailures(BaseModel):
    phrase: str
    failures: int  # labelled Episodes whose Reference label fails this Phrase
    winnow_rejects: int  # of those, the ones Winnow rejected
    spark_alone_rejects: int
    too_few: bool  # fewer than MIN_PHRASE_FAILURES: counted, but too few to score


class McNemar(BaseModel):
    """Discordant pairs between Winnow and Spark alone, counts only: on the Episodes both decided,
    how many only one of them got right."""

    compared: int
    winnow_only_right: int
    spark_alone_only_right: int


class Slack(BaseModel):
    """How far the labeller's own interval edges move between the first pass and the relabel."""

    seconds: float | None  # the 95th percentile of edge disagreement; None with no edge to compare
    edges: int  # interval edges compared: a start and an end per Phrase failed in both passes
    episodes: int  # relabelled Episodes that also have a first pass


class SlackPoint(BaseModel):
    slack_s: float
    right: int  # correct Rejects whose Reason is right at this slack
    of: int  # correct Rejects


class RightReasonRow(BaseModel):
    """Of a system's correct Rejects, how many name a failing Phrase at a time inside its labelled
    interval, widened by the slack."""

    system: System
    label: str
    at_slack: Proportion | None  # at the measured slack; None without one
    curve: list[SlackPoint]  # over 0-3 s of slack


class RightReason(BaseModel):
    slack: Slack
    rows: list[RightReasonRow]


class RiskPoint(BaseModel):
    """The Episodes a system is at least this sure about, and how many of them it gets wrong."""

    confidence: float  # the lowest confidence covered
    covered: int
    errors: int  # covered Episodes whose leaning side disagrees with the Reference label


class RiskCoverage(BaseModel):
    system: System
    label: str
    episodes: int  # every labelled Episode, so coverage = covered / episodes
    points: list[RiskPoint]  # most confident first; Episodes tied in confidence enter together


class MatchedRow(BaseModel):
    system: System
    label: str
    covered: int  # Episodes it decides at the matched coverage
    keep_precision: Proportion  # its Keeps there that meet the Description, of its Keeps


class MatchedCoverage(BaseModel):
    """Keep precision with Spark alone held to Winnow's coverage: its most confident Episodes,
    never splitting a tie, so it covers at most `target`."""

    target: int  # the Episodes Winnow decides without a person
    episodes: int
    rows: list[MatchedRow]


class EvaluationRequest(BaseModel):
    set_name: SetName
    rubric_version: int | None = Field(default=None, ge=1)  # None: the latest version


class EvaluationReport(BaseModel):
    set_name: SetName
    rubric_version: int
    episodes: int  # in the set
    labelled: int  # with a first-pass Reference label; only these are scored
    description_failures: int  # labelled Episodes whose Reference label fails a Phrase
    comparison: Comparison
    right_reason: RightReason
    risk_coverage: list[RiskCoverage]  # Winnow, then Spark alone
    matched_coverage: MatchedCoverage
    mcnemar: McNemar
    phrase_failures: list[PhraseFailures]  # in the frozen Description's order
    ablation: list[AblationRow]  # robot data only; + SAM; + Spark visual; all
    tracking_health: list[TrackHealthRow]  # wrist, then exterior
    cost: MetaCost
    review_time: ReviewTime
    dataset_outcome: DatasetOutcome
    failbench: FailBenchCheck


class TestRun(BaseModel):
    """One logged Test set run: the reported numbers are the last of these before the freeze."""

    __test__ = False  # not a pytest class

    id: int
    run_at: str
    rubric_version: int
    report: EvaluationReport
