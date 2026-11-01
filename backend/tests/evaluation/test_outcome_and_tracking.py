"""SAM tracking health per track type, the Dataset outcome against Reference labels, and the
FailBench check against the Dataset outcome."""

import pytest

from tests.evaluation.labelled import case
from winnow.baseline.prompts import FROZEN
from winnow.evaluation.cases import TrackCheck
from winnow.evaluation.dataset_outcome import dataset_outcome, failbench_check
from winnow.evaluation.tracking_health import tracking_health

FIRST_TRY, NEVER_DROPS = FROZEN.phrases[:2]
HEALTHY = TrackCheck(lost=False, review_signal=False)
LOST = TrackCheck(lost=True, review_signal=True)


def test_tracking_health_counts_lost_tracks_and_the_needs_review_they_left_per_track_type():
    cases = [
        case(0, None, "keep", tracks={"wrist": HEALTHY, "exterior": HEALTHY}),
        case(1, None, "needs_review", tracks={"wrist": HEALTHY, "exterior": LOST}),
        # Lost, but the Episode was rejected anyway on a grasp failure.
        case(2, FIRST_TRY, "reject", tracks={"wrist": LOST, "exterior": LOST}, too_small=True),
        # Lost where no hard Criterion read it: no Needs review it caused.
        case(3, None, "needs_review", tracks={"exterior": TrackCheck(True, False)}),
        case(4, None, "keep"),  # no track at all: the gripper never closed, and no box
    ]

    wrist, exterior = tracking_health(cases)

    assert (wrist.kind, wrist.label) == ("wrist", "Wrist object track")
    assert (wrist.lost.count, wrist.lost.of, wrist.needs_review, wrist.too_small) == (1, 3, 0, 1)
    assert exterior.kind == "exterior"
    assert (exterior.lost.count, exterior.lost.of) == (3, 4)
    assert (exterior.needs_review, exterior.too_small) == (1, 1)


def test_no_labelled_tracks_have_no_interval():
    wrist, _ = tracking_health([case(0, None, "keep")])

    assert (wrist.lost.count, wrist.lost.of, wrist.lost.low) == (0, 0, None)


OUTCOMES = [
    case(0, None, "keep", dataset_outcome=True, failbench=True),
    # droid_100 Episode 42's story: the dataset calls it a success; the Description fails it.
    case(42, NEVER_DROPS, "reject", dataset_outcome=True, failbench=True),
    case(2, FIRST_TRY, "reject", dataset_outcome=False, failbench=True),
    case(5, FIRST_TRY, "reject", dataset_outcome=False, failbench=False),
    case(7, None, "keep", dataset_outcome=False, failbench=None),  # a failure that meets it
    case(9, None, "keep", dataset_outcome=None, failbench=True),  # the source ships no flag
]


def test_the_dataset_outcome_table_crosses_the_outcome_with_the_reference_label():
    table = dataset_outcome(OUTCOMES)

    assert (table.compared, table.no_outcome) == (5, 1)
    assert (table.success_meets, table.success_fails) == (1, 1)
    assert (table.failure_meets, table.failure_fails) == (1, 2)
    assert [(d.episode_id, d.dataset_outcome, d.failed_phrases) for d in table.disagreements] == [
        ("droid_100:42", True, [NEVER_DROPS]),
        ("droid_100:7", False, []),
    ]


def test_the_failbench_check_is_scored_against_the_dataset_outcome():
    check = failbench_check(OUTCOMES)

    # Answered with an outcome: Episodes 0, 42 (successes), 2 and 5 (failures).
    assert check.answered == 4
    assert (check.agrees.count, check.agrees.of) == (3, 4)
    assert (check.failures_caught.count, check.failures_caught.of) == (1, 2)
    assert check.balanced_accuracy == pytest.approx((1 / 2 + 2 / 2) / 2)


def test_without_answers_the_failbench_check_scores_nothing():
    check = failbench_check([case(0, None, "keep", dataset_outcome=True)])

    assert (check.answered, check.agrees.of, check.balanced_accuracy) == (0, 0, None)
