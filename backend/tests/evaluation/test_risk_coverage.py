"""Risk–coverage curves from each system's confidence, and Keep precision at matched coverage, so
Winnow abstaining more can't pass for a win. Expected values are worked by hand."""

from winnow.baseline.prompts import FROZEN
from winnow.evaluation.cases import EvaluationCase, Ranking, SparkDecision
from winnow.evaluation.risk_coverage import matched_coverage, risk_coverage
from winnow.reference_labels.models import FailInterval
from winnow.triage.models import TriageDecision

FIRST_TRY = FROZEN.phrases[0]


def case(
    n: int,
    failure: bool,
    winnow: TriageDecision,
    winnow_ranking: Ranking,
    spark: SparkDecision | None = "keep",
    spark_ranking: Ranking | None = None,
) -> EvaluationCase:
    return EvaluationCase(
        episode_id=f"droid_100:{n}",
        duration_s=10.0,
        failed={FIRST_TRY: FailInterval(start_s=0, end_s=1)} if failure else {},
        winnow=winnow,
        spark_alone=spark,
        winnow_claim=None,
        spark_alone_claim=None,
        winnow_ranking=winnow_ranking,
        spark_alone_ranking=spark_ranking or Ranking("keep", 0.6),
    )


def test_a_risk_coverage_point_counts_errors_among_the_most_confident_episodes():
    cases = [
        case(0, True, "reject", Ranking("reject", 0.95)),
        case(1, False, "keep", Ranking("keep", 0.95)),
        case(2, True, "needs_review", Ranking("keep", 0.8)),  # leans the wrong way
        case(3, False, "needs_review", Ranking("reject", 0.6)),  # so does this one
        case(4, True, "reject", Ranking("reject", 0.6)),
    ]

    winnow = {curve.system: curve for curve in risk_coverage(cases)}["winnow"]

    assert winnow.episodes == 5
    points = [(p.confidence, p.covered, p.errors) for p in winnow.points]
    # Ties enter together: 0.6 covers Episodes 3 and 4 at once.
    assert points == [(0.95, 2, 0), (0.8, 3, 1), (0.6, 5, 2)]


def test_stated_confidence_breaks_ties_in_spark_alones_agreement_score():
    cases = [
        case(0, False, "keep", Ranking("keep", 0.95), "keep", Ranking("keep", 0.8, 0.7)),
        case(1, True, "keep", Ranking("keep", 0.95), "keep", Ranking("keep", 0.8, 0.9)),
    ]

    spark = {curve.system: curve for curve in risk_coverage(cases)}["spark_alone"]

    assert [(p.covered, p.errors) for p in spark.points] == [(1, 1), (2, 1)]


def matched_cases(last: TriageDecision) -> list[EvaluationCase]:
    sure = Ranking("keep", 0.9)  # Winnow's ranking plays no part in matched coverage
    return [
        case(0, True, "reject", sure, "keep", Ranking("keep", 0.95, 0.9)),  # Spark's false keep
        case(1, False, "keep", sure, "keep", Ranking("keep", 0.95, 0.8)),
        case(2, True, "keep", sure, "reject", Ranking("reject", 0.8, 0.8)),  # Winnow's false keep
        case(3, False, "needs_review", sure, "reject", Ranking("reject", 0.8, 0.8)),
        case(4, True, "needs_review", sure, "keep", Ranking("keep", 0.6)),
        case(5, False, last, sure, "keep", Ranking("keep", 0.6)),
    ]


def test_keep_precision_is_compared_at_winnows_own_coverage():
    matched = matched_coverage(matched_cases(last="keep"))

    assert (matched.target, matched.episodes) == (4, 6)  # Winnow decides 4 of 6 Episodes
    rows = {row.system: row for row in matched.rows}
    winnow, spark = rows["winnow"], rows["spark_alone"]
    assert winnow.covered == 4
    assert (winnow.keep_precision.count, winnow.keep_precision.of) == (2, 3)  # Episodes 1, 5
    # Spark alone covers its 4 most confident Episodes, 0 to 3, and keeps 0 and 1.
    assert spark.covered == 4
    assert (spark.keep_precision.count, spark.keep_precision.of) == (1, 2)


def test_matched_coverage_never_splits_a_tie_so_it_may_cover_fewer():
    matched = matched_coverage(matched_cases(last="needs_review"))

    spark = {row.system: row for row in matched.rows}["spark_alone"]
    assert matched.target == 3
    assert spark.covered == 2  # Episodes 2 and 3 tie, and both would overshoot
    assert (spark.keep_precision.count, spark.keep_precision.of) == (1, 2)
