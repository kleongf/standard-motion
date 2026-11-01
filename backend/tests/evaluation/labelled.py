"""A labelled Episode as the report sees it, built by hand for the protocol sections' tests."""

from winnow.evaluation.cases import Claim, EvaluationCase, Ranking
from winnow.reference_labels.models import FailInterval
from winnow.triage.models import TriageDecision


def case(
    n: int,
    phrase: str | None,
    winnow: TriageDecision,
    claim: Claim | None = None,
    **facts: object,
) -> EvaluationCase:
    """Fixture Episode n, failing `phrase` from 1 to 2 s (or meeting the Description with None),
    and what Winnow decided; `facts` sets the case's other fields."""
    failed = {} if phrase is None else {phrase: FailInterval(start_s=1.0, end_s=2.0)}
    return EvaluationCase(
        episode_id=f"droid_100:{n}",
        duration_s=3.0,
        failed=failed,
        winnow=winnow,
        spark_alone=None,
        winnow_claim=claim,
        spark_alone_claim=None,
        winnow_ranking=Ranking("reject", 0.5),
        spark_alone_ranking=Ranking("reject", 0.5),
        **facts,  # type: ignore[arg-type]
    )
