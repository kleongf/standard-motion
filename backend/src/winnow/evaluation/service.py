"""The evaluation: (set, Rubric version) -> report, over the set's Reference-labelled Episodes.

Reference labels are read here and nowhere in scoring. Only Episodes the blind gate reveals
(those with a first-pass Reference label) are scored, and only aggregates and labels leave this
module: no per-Episode decision is in the report. Interview and review labels tune the
Rubric on the Dev set, so they are applied to Dev set Episodes only, never to the Test set; the
margin multiplier s they calibrate is the version's, so it scores both.
Everything is re-scored from stored facts and answers, so a report makes no Meta call.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from winnow.baseline.models import EpisodeBaseline
from winnow.baseline.prompts import FROZEN
from winnow.core.context import AppContext
from winnow.criteria.facts import EpisodeFacts
from winnow.episodes.models import Episode
from winnow.evaluation.ablation import ablation
from winnow.evaluation.cases import (
    EvaluationCase,
    failed_phrases,
    spark_alone_claim,
    spark_alone_decision,
    spark_alone_ranking,
    winnow_claim,
    winnow_ranking,
)
from winnow.evaluation.comparison import comparison, mcnemar, phrase_failures
from winnow.evaluation.cost import meta_cost, review_time
from winnow.evaluation.dataset_outcome import dataset_outcome, failbench_check
from winnow.evaluation.models import EvaluationReport, EvaluationRequest
from winnow.evaluation.right_reason import measured_slack, right_reason
from winnow.evaluation.risk_coverage import matched_coverage, risk_coverage
from winnow.evaluation.tracking_health import track_checks, tracking_health
from winnow.meta.costs import CostLog
from winnow.reference_labels.gate import revealed_ids
from winnow.reference_labels.models import ReferenceLabel
from winnow.rubric.models import Rubric, RubricVersion
from winnow.sets.models import SetName
from winnow.triage.confidence import UNCALIBRATED
from winnow.triage.models import Label
from winnow.triage.scoring import score
from winnow.triage.service import episode_facts


class UnknownRubricVersionError(LookupError):
    pass


def _version(ctx: AppContext, rubric_version: int | None) -> RubricVersion:
    if rubric_version is None:
        return ctx.rubrics.latest()
    version = ctx.rubrics.get(rubric_version)
    if version is None:
        raise UnknownRubricVersionError(f"There is no Rubric v{rubric_version}")
    return version


@dataclass(frozen=True)
class Labelled:
    """One labelled Episode and everything stored about it, read once and scored as often as
    the report needs."""

    episode: Episode
    facts: EpisodeFacts
    label: ReferenceLabel
    labels: Sequence[Label]  # interview and review labels applied to it
    baseline: EpisodeBaseline
    too_small: bool


def _labelled(ctx: AppContext, label: ReferenceLabel, labels: Sequence[Label]) -> Labelled:
    episode = ctx.episodes.get(label.episode_id)
    assert episode is not None  # a Reference label names an ingested Episode
    candidate = ctx.selection.get(episode.id)
    return Labelled(
        episode=episode,
        facts=episode_facts(ctx, episode),
        label=label,
        labels=labels,
        baseline=ctx.baseline.answers(episode.id, FROZEN.text),
        too_small=candidate is not None and candidate.exclusion_reason == "object too small to see",
    )


def case(item: Labelled, rubric: Rubric, s: float = UNCALIBRATED) -> EvaluationCase:
    triage = score(rubric, item.facts, item.labels, s)
    failbench = item.baseline.failbench
    return EvaluationCase(
        episode_id=item.episode.id,
        duration_s=item.episode.duration_s,
        failed=failed_phrases(item.label),
        winnow=triage.decision,
        spark_alone=spark_alone_decision(item.baseline),
        winnow_claim=winnow_claim(triage),
        spark_alone_claim=spark_alone_claim(item.baseline),
        winnow_ranking=winnow_ranking(triage),
        spark_alone_ranking=spark_alone_ranking(item.baseline),
        dataset_outcome=item.episode.dataset_outcome,
        failbench=None
        if failbench is None or failbench.answer is None
        else failbench.answer.success,
        elapsed_s=item.label.elapsed_s,
        tracks=track_checks(item.facts, triage),
        too_small=item.too_small,
    )


def evaluation_report(
    ctx: AppContext,
    set_name: SetName,
    rubric_version: int | None = None,
) -> EvaluationReport:
    version = _version(ctx, rubric_version)
    members = ctx.sets.get(set_name).episode_ids
    revealed = revealed_ids(ctx)  # the blind gate: only these Episodes' outputs are read
    first_pass = {
        label.episode_id: label
        for label in ctx.reference_labels.list()
        if not label.relabel and label.episode_id in revealed
    }

    def applied(episode_id: str) -> Sequence[Label]:
        return () if set_name == "test" else ctx.labels.in_force(episode_id)

    items = [_labelled(ctx, first_pass[id], applied(id)) for id in members if id in first_pass]

    s = ctx.calibrations.s_for(version.version)  # tuned on the Dev set's labels alone

    def scored(rubric: Rubric) -> list[EvaluationCase]:
        return [case(item, rubric, s) for item in items]

    cases = scored(version.rubric)
    costs = CostLog(ctx.settings.cost_log_path, ctx.settings.meta_budget_usd)  # read, never spent
    slack = measured_slack(ctx.reference_labels.list())
    return EvaluationReport(
        set_name=set_name,
        rubric_version=version.version,
        episodes=len(members),
        labelled=len(cases),
        description_failures=sum(c.description_failure for c in cases),
        comparison=comparison(cases),
        right_reason=right_reason(cases, slack),
        risk_coverage=risk_coverage(cases),
        matched_coverage=matched_coverage(cases),
        mcnemar=mcnemar(cases),
        phrase_failures=phrase_failures(cases, FROZEN.phrases),
        ablation=ablation(version.rubric, scored, slack),
        tracking_health=tracking_health(cases),
        cost=meta_cost(costs.entries(), members),
        review_time=review_time(cases),
        dataset_outcome=dataset_outcome(cases),
        failbench=failbench_check(cases),
    )


def run_evaluation(ctx: AppContext, request: EvaluationRequest) -> EvaluationReport:
    """The report; a Test set run is also appended to the Test run log."""
    report = evaluation_report(ctx, request.set_name, request.rubric_version)
    if request.set_name == "test":
        ctx.test_runs.append(report)
    return report
