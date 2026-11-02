"""A labelled Episode as the report sees it, built by hand for the protocol sections' tests."""

from standard_motion.evaluation.cases import Claim, EvaluationCase, Ranking
from standard_motion.reference_labels.models import FailInterval
from standard_motion.triage.models import TriageDecision


def case(
    n: int,
    phrase: str | None,
    standard_motion: TriageDecision,
    claim: Claim | None = None,
    **facts: object,
) -> EvaluationCase:
    """Fixture Episode n, failing `phrase` from 1 to 2 s (or meeting the Description with None),
    and what Standard Motion decided; `facts` sets the case's other fields."""
    failed = {} if phrase is None else {phrase: FailInterval(start_s=1.0, end_s=2.0)}
    return EvaluationCase(
        episode_id=f"droid_100:{n}",
        duration_s=3.0,
        failed=failed,
        standard_motion=standard_motion,
        spark_alone=None,
        standard_motion_claim=claim,
        spark_alone_claim=None,
        standard_motion_ranking=Ranking("reject", 0.5),
        spark_alone_ranking=Ranking("reject", 0.5),
        **facts,  # type: ignore[arg-type]
    )
