"""The source ablation: Winnow re-scored with only some sources' Criteria, each row's false keeps,
right reason and coverage counted against Reference labels."""

from collections.abc import Sequence

from tests.evaluation.labelled import case
from winnow.baseline.prompts import FROZEN
from winnow.evaluation.ablation import MASKS, ablation, masked
from winnow.evaluation.cases import Claim, EvaluationCase
from winnow.evaluation.models import Slack
from winnow.evaluation.protocol_models import SourceMask
from winnow.evaluation.stats import Proportion
from winnow.rubric.models import Rubric
from winnow.rubric.seed import SEEDED
from winnow.triage.models import TriageDecision

FIRST_TRY, NEVER_DROPS, PLACES = FROZEN.phrases[:3]
SLACK = Slack(seconds=0.5, edges=2, episodes=1)


def kept(mask: SourceMask) -> list[str]:
    return [c.id for c in masked(SEEDED, MASKS[mask][1]).criteria]


def test_each_mask_keeps_only_the_criteria_reading_its_sources():
    assert kept("robot_data") == ["grasp-attempts", "release-height", "longest-pause"]
    assert kept("robot_data_sam") == [
        "grasp-attempts",
        "in-hand-lost",
        "fall-after-release",
        "release-height",
        "final-overlap",
        "longest-pause",
    ]
    assert kept("robot_data_visual") == [
        "grasp-attempts",
        "release-height",
        "placed-on-target",
        "longest-pause",
    ]
    assert kept("all") == [c.id for c in SEEDED.criteria]
    assert masked(SEEDED, MASKS["robot_data"][1]).phrases == SEEDED.phrases  # none dropped


def scored(rubric: Rubric) -> list[EvaluationCase]:
    """Four labelled Episodes, decided by whichever Criteria the Rubric still has: a grasp
    failure robot data catches, a drop only the wrist track sees, a misplacement only Spark's
    visual question sees (SAM's target box is lost on it), and an Episode meeting the
    Description that needs review until Spark confirms its placement."""
    ids = {c.id for c in rubric.criteria}

    def seen_by(criterion: str, phrase: str, at_s: float) -> tuple[TriageDecision, Claim | None]:
        return ("reject", Claim(phrase, at_s)) if criterion in ids else ("keep", None)

    # At 3.0 s: outside the labelled 1-2 s even widened by the 0.5 s slack.
    return [
        case(0, FIRST_TRY, *seen_by("grasp-attempts", FIRST_TRY, 1.2)),
        case(1, NEVER_DROPS, *seen_by("in-hand-lost", NEVER_DROPS, 1.5)),
        case(2, PLACES, *seen_by("placed-on-target", PLACES, 3.0)),
        case(3, None, "keep" if "placed-on-target" in ids else "needs_review", None),
    ]


Counts = tuple[int, int]


def counts(p: Proportion | None) -> Counts | None:
    return None if p is None else (p.count, p.of)


def rows() -> dict[SourceMask, tuple[Counts | None, Counts | None, Counts | None, int]]:
    """(false keeps, right reason, coverage, Criteria kept) per mask."""
    return {
        r.mask: (counts(r.false_keeps), counts(r.right_reason), counts(r.coverage), r.criteria)
        for r in ablation(SEEDED, scored, SLACK)
    }


def test_each_row_counts_false_keeps_right_reason_and_coverage_for_its_sources():
    assert rows() == {
        # Misses the drop and the misplacement; the good Episode waits for a person.
        "robot_data": ((2, 3), (1, 1), (3, 4), 3),
        "robot_data_sam": ((1, 3), (2, 2), (3, 4), 6),
        # Spark sees the misplacement, but at 3.0 s, outside its labelled interval.
        "robot_data_visual": ((1, 3), (1, 2), (4, 4), 4),
        "all": ((0, 3), (2, 3), (4, 4), 7),
    }


def test_rows_come_in_order_with_labels_and_the_rubrics_size():
    table = ablation(SEEDED, scored, SLACK)

    assert [r.label for r in table] == [
        "Robot data only",
        "Robot data + SAM",
        "Robot data + Spark visual",
        "All sources",
    ]
    assert {r.of for r in table} == {7}


def test_without_a_slack_right_reason_is_not_scored():
    no_slack = Slack(seconds=None, edges=0, episodes=0)

    assert all(r.right_reason is None for r in ablation(SEEDED, scored, no_slack))


def test_the_ablation_scores_the_rubric_once_per_mask():
    seen: list[Sequence[str]] = []

    def watched(rubric: Rubric) -> list[EvaluationCase]:
        seen.append([c.id for c in rubric.criteria])
        return scored(rubric)

    ablation(SEEDED, watched, SLACK)

    assert [len(ids) for ids in seen] == [3, 6, 4, 7]
