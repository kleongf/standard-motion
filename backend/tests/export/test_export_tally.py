"""Why an export would write no Episode: each cause in turn, and none while it writes some or
could, with Episodes awaiting a Reference label."""

from standard_motion.export.models import DecisionCounts
from standard_motion.export.tally import exported_count, nothing_exported


def counts(
    keep: int = 0, needs_review: int = 0, reject: int = 0, awaiting: int = 0, test_set: int = 0
) -> DecisionCounts:
    return DecisionCounts(
        keep=keep,
        needs_review=needs_review,
        reject=reject,
        awaiting_label=awaiting,
        test_set=test_set,
    )


def test_needs_review_counts_only_when_included():
    assert exported_count(counts(keep=2, needs_review=3), "keep") == 2
    assert exported_count(counts(keep=2, needs_review=3), "keep_and_review") == 5


def test_nothing_to_say_while_something_is_exported_or_awaits_its_label():
    assert nothing_exported(counts(keep=1), "keep", ran=True) is None
    assert nothing_exported(counts(needs_review=1), "keep_and_review", ran=True) is None
    assert nothing_exported(counts(reject=3, awaiting=1), "keep", ran=False) is None


def test_no_episodes_at_all_or_only_test_set_ones():
    assert nothing_exported(counts(), "keep", ran=True) == (
        "No Episodes yet: ingest some on the Prepare page."
    )
    assert nothing_exported(counts(test_set=4), "keep", ran=True) == (
        "Every Episode is in the Test set, which is never exported."
    )


def test_no_run_yet_before_the_rubric_is_blamed():
    assert nothing_exported(counts(reject=2, needs_review=1), "keep", ran=False) == (
        "No Rubric has been Run yet, and the starter Rubric keeps none of these Episodes: "
        "run one on Describe & run."
    )


def test_every_episode_rejected_or_left_out_as_needs_review():
    assert nothing_exported(counts(reject=3, test_set=1), "keep", ran=True) == (
        "Every Episode outside the Test set was rejected."
    )
    assert nothing_exported(counts(reject=2, needs_review=1), "keep", ran=True) == (
        "No Episode outside the Test set is kept: 2 rejected, 1 Needs review. "
        "Include Needs review to export those."
    )
