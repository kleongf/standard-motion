"""Where Spark alone and Winnow disagree, live: every Reference-labelled Episode whose Triage
decision, as the Workstation shows it now (the latest Rubric version, labels in force), differs
from Spark alone's majority answer. The Evaluation page is the only place this contrast shows;
an Episode whose outputs the blind gate still hides is never listed."""

from winnow.baseline.models import EpisodeBaseline
from winnow.baseline.prompts import FROZEN
from winnow.core.context import AppContext
from winnow.evaluation.cases import failed_phrases, spark_alone_decision
from winnow.evaluation.protocol_models import Disagreement
from winnow.reference_labels.gate import revealed_episodes
from winnow.triage.models import TriageDecision
from winnow.triage.service import plain_reason, scored


def _majority_reason(baseline: EpisodeBaseline) -> str | None:
    side = spark_alone_decision(baseline)
    answers = [s.answer for s in baseline.samples if s.answer is not None]
    return next((a.reason for a in answers if a.decision == side), None)


def differ(winnow: TriageDecision, spark_alone: str | None) -> bool:
    """Needs review and an even split both decide nothing, so only they agree with each other."""
    return (None if winnow == "needs_review" else winnow) != spark_alone


def disagreements(ctx: AppContext) -> list[Disagreement]:
    """Both decided but differently first, then Winnow or Spark alone undecided; Episodes in
    Dataset order within each. An Episode Spark alone has no answer for is left out."""
    episodes = revealed_episodes(ctx)
    if not episodes:
        return []
    _, triages = scored(ctx, episodes)
    sets = ctx.sets.sets_of([e.id for e in episodes])
    first_pass = {r.episode_id: r for r in ctx.reference_labels.list() if not r.relabel}
    rows: list[Disagreement] = []
    for triage in triages:
        baseline = ctx.baseline.answers(triage.episode_id, FROZEN.text)
        if not any(s.answer for s in baseline.samples):
            continue
        spark = spark_alone_decision(baseline)
        if not differ(triage.decision, spark):
            continue
        rows.append(
            Disagreement(
                episode_id=triage.episode_id,
                set_name=sets.get(triage.episode_id),
                winnow=triage.decision,
                winnow_reason=plain_reason(triage),
                spark_alone=spark,
                spark_alone_reason=_majority_reason(baseline),
                failed_phrases=list(failed_phrases(first_pass[triage.episode_id])),
            )
        )
    return sorted(rows, key=lambda r: r.winnow == "needs_review" or r.spark_alone is None)
