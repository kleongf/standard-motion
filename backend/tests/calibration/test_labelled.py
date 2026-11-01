"""What calibration reads off labelled anchor Episodes: each labelled (Episode, Phrase) pair's
errors at every s, and threshold suggestions where two or more labels contradict a Criterion."""

from typing import Literal

import numpy as np

from tests.triage.robot_data import CLEAN_GRIPPER, FIRST_TRY, PLACES, facts, rubric
from winnow.calibration.labelled import LabelledEpisode, patterns, suggestions
from winnow.criteria.facts import EpisodeFacts
from winnow.criteria.models import Criterion
from winnow.triage.models import Label
from winnow.triage.scoring import score

RISING = np.linspace(0, 0.1, 45).tolist()


def overshooting(by: float) -> EpisodeFacts:
    """Out to 0.3 + `by` along x and back to 0.3: the further, the less efficient the path."""
    x = np.concatenate([np.linspace(0, 0.3 + by, 30), np.linspace(0.3 + by, 0.3, 15)])
    return facts(CLEAN_GRIPPER, RISING, x.tolist())


# Path efficiency on each, against the ratio's 0.05 noise floor.
EFFICIENCY = {"a": 0.617, "b": 0.518, "c": 0.348, "d": 0.927, "e": 0.757}
FACTS = {
    "a": overshooting(0.1),
    "b": overshooting(0.15),
    "c": overshooting(0.3),
    "d": overshooting(0.0),
    "e": overshooting(0.05),
}


def efficient(threshold: float, id: str = "path", hard: bool = True) -> Criterion:
    return Criterion(
        id=id,
        phrase=PLACES,
        primitive="path_efficiency",
        comparator=">=",
        threshold=threshold,
        unit="ratio",
        hard=hard,
    )


def labelled(**values: Literal["pass", "fail"]) -> list[LabelledEpisode]:
    """Each Episode with one review label on PLACES."""
    return [
        LabelledEpisode(id_, FACTS[id_], [Label(phrase=PLACES, value=v, source="review")])
        for id_, v in values.items()
    ]


def test_the_fixture_paths_have_the_efficiencies_the_tests_assume():
    for id_, value in EFFICIENCY.items():
        assert score(rubric(efficient(0.5)), FACTS[id_]).criteria[0].value == value


def test_a_pair_is_wrong_at_each_s_its_crisp_phrase_result_contradicts_its_label():
    # Against ≥ 0.7 the effective margin is 0.05 * s: 0.1, 0.075, 0.05, 0.0375, 0.025.
    found = patterns(rubric(efficient(0.7)), labelled(a="pass", b="fail", d="pass", e="fail"))

    assert found == [
        (False, True, True, True, True),  # 0.617, 0.083 below: unsure only at s = 2
        (False, False, False, False, False),  # 0.518 fails, as labelled
        (False, False, False, False, False),  # 0.927 passes, as labelled
        (False, False, True, True, True),  # 0.757, 0.057 above: unsure at s = 2 and 1.5
    ]


def test_only_labels_on_checked_phrases_of_the_rubric_are_pairs():
    labels = [
        Label(phrase=PLACES, value="pass", source="interview"),
        Label(phrase=FIRST_TRY, value="fail", source="review"),  # nothing checks it
        Label(phrase="an older Phrase", value="fail", source="review"),
    ]

    assert patterns(rubric(efficient(0.7)), [LabelledEpisode("d", FACTS["d"], labels)]) == [
        (False,) * 5
    ]


def test_two_contradicting_labels_suggest_the_midpoint_between_the_closest_pass_and_fail():
    # 0.617 and 0.518 fail ≥ 0.7 but are labelled pass; the closest fail label is 0.348.
    [suggestion] = suggestions(
        rubric(efficient(0.7)), labelled(a="pass", b="pass", c="fail", d="pass"), s=1.0
    )

    assert suggestion.criterion_id == "path"
    assert (suggestion.contradicting, suggestion.labelled) == (2, 4)
    assert suggestion.threshold == 0.7
    assert suggestion.suggested_threshold == round((0.518 + 0.348) / 2, 6)
    assert suggestion.suggested_margin == round(0.518 - 0.348, 6)
    assert suggestion.english == "Path efficiency (straight line over path) ≥ 0.70"
    assert suggestion.suggested_english == "Path efficiency (straight line over path) ≥ 0.43"


def test_one_contradicting_label_suggests_nothing():
    assert suggestions(rubric(efficient(0.7)), labelled(a="pass", c="fail", d="pass"), 1.0) == []


def test_unsure_is_not_a_contradiction():
    # 0.617 is within 0.05 of 0.65, so unsure: only 0.518 contradicts.
    assert suggestions(rubric(efficient(0.65)), labelled(a="pass", b="pass", c="fail"), 1.0) == []


def test_a_wider_s_leaves_fewer_contradictions():
    labels = labelled(a="fail", e="fail", d="pass")
    at = {s: suggestions(rubric(efficient(0.55)), labels, s) for s in (1.0, 2.0)}

    # 0.617 and 0.757 pass ≥ 0.55 crisply at s = 1; at 2 the 0.1 margin makes 0.617 unsure.
    assert [s.contradicting for s in at[1.0]] == [2]
    assert at[2.0] == []


def test_a_fail_label_another_criterion_explains_contradicts_nothing():
    # The strict Criterion fails 0.617 and 0.518 conclusively, as labelled; the loose one
    # passing them isn't what the labels disagree with. Alone, the loose one is contradicted.
    loose, strict = efficient(0.3, id="loose"), efficient(0.9, id="strict")
    labels = labelled(a="fail", b="fail", d="pass")

    assert suggestions(rubric(loose, strict), labels, 1.0) == []
    [alone] = suggestions(rubric(loose), labels, 1.0)
    assert (alone.criterion_id, alone.contradicting) == ("loose", 2)


def test_soft_criteria_get_no_suggestion():
    soft = efficient(0.7, hard=False)

    assert suggestions(rubric(soft), labelled(a="pass", b="pass", c="fail"), 1.0) == []


def test_overlapping_labels_suggest_nothing():
    # 0.617 and 0.518 fail ≥ 0.7 but are labelled pass, and 0.757 passes but is labelled fail:
    # no threshold on path efficiency puts the passes on one side and the fails on the other.
    # Bracketing alone would say ≥ 0.64, which fails both passes and passes the fail.
    labels = labelled(a="pass", b="pass", e="fail", c="fail")

    assert suggestions(rubric(efficient(0.7)), labels, 1.0) == []
