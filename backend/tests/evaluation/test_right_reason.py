"""Right reason: the slack measured from the labeller's own relabel pass, and whether each correct
Reject's Reason names a failing Phrase at a time inside its labelled interval, widened by that
slack. Expected values are worked by hand."""

import pytest

from winnow.baseline.prompts import FROZEN
from winnow.evaluation.cases import Claim, EvaluationCase, Ranking, SparkDecision, frozen_phrase
from winnow.evaluation.models import Slack
from winnow.evaluation.right_reason import measured_slack, right_reason
from winnow.reference_labels.models import FailInterval, PhraseLabel, ReferenceLabel
from winnow.triage.models import TriageDecision

FIRST_TRY, NEVER_DROPS, PLACES, NO_PAUSES = FROZEN.phrases


def label(episode: int, *, relabel: bool = False, **fails: tuple[float, float]) -> ReferenceLabel:
    """A Reference label failing the Phrases named by keyword (first_try, places, ...)."""
    by_name = {"first_try": FIRST_TRY, "drops": NEVER_DROPS, "places": PLACES, "pauses": NO_PAUSES}
    failing = {by_name[name]: interval for name, interval in fails.items()}
    return ReferenceLabel(
        episode_id=f"droid_100:{episode}",
        relabel=relabel,
        description=FROZEN.text,
        phrases=[
            PhraseLabel(
                phrase=p,
                passed=p not in failing,
                interval=FailInterval(start_s=failing[p][0], end_s=failing[p][1])
                if p in failing
                else None,
            )
            for p in FROZEN.phrases
        ],
        instruction=None,
        elapsed_s=10,
        labelled_at="2026-10-30T10:00:00+00:00",
    )


def test_the_slack_is_the_95th_percentile_of_interval_edge_disagreement():
    labels = [
        label(0, first_try=(1.0, 2.0)),
        label(0, relabel=True, first_try=(1.0, 2.2)),  # edges differ by 0 and 0.2
        label(1, places=(5.0, 6.0), pauses=(3.0, 4.0)),
        label(1, relabel=True, places=(5.4, 7.0), pauses=(1.0, 4.0)),  # 0.4, 1.0; 2.0, 0
        label(2, first_try=(0.0, 1.0)),
        label(2, relabel=True),  # a pass on the relabel has no edge to compare
        label(3, first_try=(0.0, 9.0)),  # never relabelled
    ]

    slack = measured_slack(labels)

    # Edges sorted: 0, 0, 0.2, 0.4, 1.0, 2.0. The 95th percentile sits at rank 0.95 * 5 = 4.75,
    # three quarters of the way from 1.0 to 2.0.
    assert slack.seconds == pytest.approx(1.75)
    assert (slack.edges, slack.episodes) == (6, 3)


def test_without_a_relabelled_interval_there_is_no_slack():
    slack = measured_slack([label(0, first_try=(1.0, 2.0)), label(0, relabel=True)])

    assert slack.seconds is None
    assert (slack.edges, slack.episodes) == (0, 1)


def test_a_rubric_phrase_is_read_as_the_frozen_phrase_it_overlaps_most():
    # A compiled Rubric may split the Description differently from the frozen Phrases that
    # Reference labels are given per; Winnow's claim is matched on the frozen one.
    assert frozen_phrase(FIRST_TRY) == FIRST_TRY
    assert frozen_phrase("grasps the object") == FIRST_TRY
    assert frozen_phrase("the target named in the instruction, no long") == PLACES
    assert frozen_phrase("Expert pick-and-place") is None  # overlaps no frozen Phrase
    assert frozen_phrase("never spills") is None  # not in the Description


def case(
    n: int,
    fails: dict[str, tuple[float, float]],
    winnow: TriageDecision,
    winnow_says: Claim | None,
    spark: SparkDecision | None,
    spark_says: Claim | None,
) -> EvaluationCase:
    return EvaluationCase(
        episode_id=f"droid_100:{n}",
        duration_s=10.0,
        failed={p: FailInterval(start_s=a, end_s=b) for p, (a, b) in fails.items()},
        winnow=winnow,
        spark_alone=spark,
        winnow_claim=winnow_says,
        spark_alone_claim=spark_says,
        winnow_ranking=Ranking(lean="reject", confidence=0.9),
        spark_alone_ranking=Ranking(lean="reject", confidence=0.9),
    )


FIRST_TRY_LATE = Claim(FIRST_TRY, 2.5)
CASES = [
    # Both reject a first-try failure; Winnow says so 0.5 s after the labelled interval.
    case(0, {FIRST_TRY: (1.0, 2.0)}, "reject", FIRST_TRY_LATE, "reject", Claim(FIRST_TRY, 1.5)),
    # Winnow names the wrong Phrase; Spark alone is 1 s early.
    case(1, {PLACES: (5.0, 6.0)}, "reject", Claim(NO_PAUSES, 5.5), "reject", Claim(PLACES, 4.0)),
    # Not a Reject from either: not scored for right reason.
    case(2, {FIRST_TRY: (0.0, 1.0)}, "needs_review", None, "keep", None),
    # A false reject: not scored for right reason.
    case(3, {}, "reject", Claim(FIRST_TRY, 1.0), "reject", Claim(FIRST_TRY, 1.0)),
    # A Reject with no time (a label-only Reject) can't be right.
    case(
        4,
        {NEVER_DROPS: (3.0, 4.0)},
        "reject",
        Claim(NEVER_DROPS, None),
        "reject",
        Claim(NEVER_DROPS, 3.5),
    ),
]


def test_right_reason_counts_correct_rejects_naming_a_failing_phrase_inside_its_interval():
    slack = Slack(seconds=0.5, edges=2, episodes=1)
    rows = {r.system: r for r in right_reason(CASES, slack).rows}

    assert list(rows) == ["winnow", "spark_alone"]
    winnow, spark = rows["winnow"].at_slack, rows["spark_alone"].at_slack
    assert winnow is not None and spark is not None
    assert (winnow.count, winnow.of) == (1, 3)  # only Episode 0, now inside by the slack
    assert (spark.count, spark.of) == (2, 3)  # Episodes 0 and 4; Episode 1 is still 0.5 s early


def test_right_reason_is_also_a_curve_over_zero_to_three_seconds_of_slack():
    slack = Slack(seconds=None, edges=0, episodes=0)
    rows = {r.system: r for r in right_reason(CASES, slack).rows}

    spark = {p.slack_s: (p.right, p.of) for p in rows["spark_alone"].curve}
    assert list(spark) == [i * 0.25 for i in range(13)]
    assert (spark[0.0], spark[0.75], spark[1.0], spark[3.0]) == ((2, 3), (2, 3), (3, 3), (3, 3))
    winnow = {p.slack_s: (p.right, p.of) for p in rows["winnow"].curve}
    assert (winnow[0.25], winnow[0.5], winnow[3.0]) == ((0, 3), (1, 3), (1, 3))
    assert rows["winnow"].at_slack is None  # no measured slack, no headline k/n
