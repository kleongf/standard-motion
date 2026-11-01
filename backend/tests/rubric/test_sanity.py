"""The Rubric sanity monitor: each hard Criterion's fail rate over the anchor pool, a warning
when it is too rare or too common, and the Episodes only it rejects."""

from collections.abc import Sequence

import numpy as np

from tests.triage.robot_data import (
    CLEAN_GRIPPER,
    CLEAN_Z,
    DOWN,
    PLACES,
    REGRASP_GRIPPER,
    REGRASP_Z,
    first_try,
    rubric,
    still,
)
from tests.triage.robot_data import (
    facts as make_facts,
)
from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.models import Criterion
from winnow.rubric.models import AnchorPreview, CriterionPreview
from winnow.rubric.preview import anchor_preview
from winnow.triage.models import Label

N_CLEAN = len(CLEAN_GRIPPER)
N_REGRASP = len(REGRASP_GRIPPER)


def clean() -> EpisodeFacts:
    """One grasp, the arm always moving: passes both Criteria."""
    return make_facts(CLEAN_GRIPPER, CLEAN_Z)


def regrasp() -> EpisodeFacts:
    """Three grasp attempts, the arm always moving: only the grasp Criterion fails."""
    return make_facts(REGRASP_GRIPPER, REGRASP_Z)


def frozen_regrasp() -> EpisodeFacts:
    """Three grasp attempts and the arm stops for 2 s in the middle: both Criteria fail."""
    x = [0.0, 0.1, 0.2, 0.3, *[0.3] * (N_REGRASP - 8), 0.4, 0.5, 0.6, 0.7]
    return make_facts(REGRASP_GRIPPER, [DOWN] * N_REGRASP, x)


def pool(*episodes: EpisodeFacts) -> dict[str, EpisodeFacts]:
    return {f"e{i}": f for i, f in enumerate(episodes)}


def preview_of(
    episodes: dict[str, EpisodeFacts],
    criteria: Sequence[Criterion],
    labels: dict[str, list[Label]] | None = None,
    s: float = 1.0,
    scored: Sequence[Criterion] | None = None,
) -> AnchorPreview:
    """`criteria` score the Rubric; `scored` (default: the same) are the ones shown."""
    base = rubric(*criteria)
    return anchor_preview(episodes, base, list(scored or criteria), None, labels or {}, s)


def found(preview: AnchorPreview, criterion_id: str) -> CriterionPreview:
    return next(c for c in preview.criteria if c.criterion_id == criterion_id)


def count(shown: CriterionPreview) -> int | None:
    return shown.fail_rate.count if shown.fail_rate else None


def test_a_criterion_that_never_fails_is_too_rare():
    shown = found(preview_of(pool(*[clean()] * 5), [first_try()]), "grasp-attempts")

    assert shown.fail_rate is not None
    assert (shown.fail_rate.count, shown.fail_rate.of) == (0, 5)
    assert shown.fail_rate.low == 0.0
    assert shown.fail_rate.high is not None and shown.fail_rate.high > 0.4
    assert shown.warning == "too_rare"
    assert shown.only_rejects == []


def test_a_criterion_that_nearly_always_fails_is_too_common():
    episodes = pool(*[regrasp()] * 20)

    shown = found(preview_of(episodes, [first_try()]), "grasp-attempts")

    assert shown.fail_rate is not None
    assert (shown.fail_rate.count, shown.fail_rate.of) == (20, 20)
    assert shown.warning == "too_common"


def test_a_fail_rate_between_the_bounds_has_no_warning_at_95_percent_or_2_percent_up():
    # 19 of 20 is exactly 95%: not above it. 1 of 50 is exactly 2%: not below it.
    nineteen = pool(*[regrasp()] * 19, clean())
    one = pool(regrasp(), *[clean()] * 49)

    assert found(preview_of(nineteen, [first_try()]), "grasp-attempts").warning is None
    assert found(preview_of(one, [first_try()]), "grasp-attempts").warning is None


def test_the_fail_rate_counts_every_anchor_episode_so_unsure_ones_are_not_failures():
    shown = found(preview_of(pool(clean(), regrasp()), [first_try()]), "grasp-attempts")

    assert shown.fail_rate is not None
    assert (shown.fail_rate.count, shown.fail_rate.of) == (1, 2)
    assert shown.warning is None


def test_an_empty_anchor_pool_has_no_rate_and_no_warning():
    shown = found(preview_of({}, [first_try()]), "grasp-attempts")

    assert shown.fail_rate is not None
    assert (shown.fail_rate.of, shown.fail_rate.low) == (0, None)
    assert shown.warning is None


def test_only_rejects_lists_the_episodes_this_criterion_alone_rejects():
    episodes = pool(clean(), regrasp(), frozen_regrasp())
    both = [first_try(), still()]

    preview = preview_of(episodes, both)

    assert preview.reject == 2
    # e1 fails only the grasp Criterion; e2 fails both, so removing either still rejects it.
    assert found(preview, "grasp-attempts").only_rejects == ["e1"]
    assert found(preview, "still").only_rejects == []
    assert count(found(preview, "still")) == 1


def test_a_label_that_passes_the_phrase_means_the_criterion_rejects_nothing():
    labels = {"e1": [Label(phrase=first_try().phrase, value="pass", source="review")]}

    preview = preview_of(pool(clean(), regrasp()), [first_try(), still()], labels)

    assert preview.reject == 0
    shown = found(preview, "grasp-attempts")
    assert (count(shown), shown.only_rejects) == (1, [])


def test_a_label_that_fails_the_phrase_of_a_passing_criterion_is_not_that_criterion_rejecting():
    # The label Rejects e0, which passes `still`. Removing `still` leaves its Phrase with no hard
    # Criterion, so the label would be ignored and e0 would stop being Rejected: but `still`
    # isn't what rejects it.
    labels = {"e0": [Label(phrase=still().phrase, value="fail", source="review")]}

    preview = preview_of(pool(clean()), [first_try(), still()], labels)

    assert preview.reject == 1
    shown = found(preview, "still")
    assert (count(shown), shown.only_rejects) == (0, [])
    assert found(preview, "grasp-attempts").only_rejects == []


def test_soft_criteria_get_no_warning_rate_or_only_rejects():
    soft = first_try(hard=False)

    shown = found(preview_of(pool(clean(), regrasp()), [soft, still()]), "grasp-attempts")

    assert (shown.fail_rate, shown.warning, shown.only_rejects) == (None, None, [])
    assert shown.failing == 1  # its counts still show


def test_a_criterion_switched_off_is_not_part_of_the_rubric_so_gets_no_warning():
    on, off = still(), first_try()

    preview = preview_of(pool(clean(), regrasp()), [on], scored=[on, off])

    assert found(preview, "grasp-attempts").fail_rate is None
    assert found(preview, "grasp-attempts").only_rejects == []
    assert found(preview, "still").warning == "too_rare"


def efficient(threshold: float, margin: float) -> Criterion:
    return Criterion(
        id="path",
        phrase=PLACES,
        primitive="path_efficiency",
        comparator=">=",
        threshold=threshold,
        unit="ratio",
        margin=margin,
    )


def test_the_margin_multiplier_changes_which_episodes_only_it_rejects():
    # A straight path has efficiency 1: against >= 1.2 it is crisp 0.2 outside a 0.08 margin at
    # s = 1, and inside the margin at s = 4. The same s decides the Episode's Triage and the
    # rescore with the Criterion removed.
    straight = make_facts(
        CLEAN_GRIPPER, np.linspace(0, 0.1, N_CLEAN).tolist(), np.linspace(0, 0.3, N_CLEAN).tolist()
    )
    path = efficient(1.2, margin=0.08)

    at_1 = preview_of(pool(straight), [path, still()], s=1.0)
    at_4 = preview_of(pool(straight), [path, still()], s=4.0)

    assert (at_1.reject, found(at_1, "path").only_rejects) == (1, ["e0"])
    assert (at_4.reject, found(at_4, "path").only_rejects) == (0, [])
    assert count(found(at_4, "path")) == 0  # unsure at s = 4, not a fail
