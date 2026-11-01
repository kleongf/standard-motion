"""Bisecting an assumed threshold over anchor Episodes with known values."""

from winnow.interview.bisection import Answered, Point, next_point, resolve, separated

# Eight anchor Episodes, 0.5 apart.
POINTS = [Point(f"droid_100:{i}", 0.5 * (i + 1)) for i in range(8)]


def bisect(threshold: float, comparator: str, fine_up_to: float) -> list[Answered]:
    """Answer each question as a curator who finds anything up to `fine_up_to` fine."""
    asked: list[Answered] = []
    while (point := next_point(POINTS, asked, threshold, comparator)) is not None:
        fine = point.value <= fine_up_to if comparator in ("<", "<=") else point.value >= fine_up_to
        asked.append(Answered(point.episode_id, point.value, fine))
    return asked


def test_it_starts_from_the_episode_nearest_the_assumed_threshold():
    assert next_point(POINTS, [], 1.9, "<") == Point("droid_100:3", 2.0)


def test_it_converges_in_at_most_three_questions_and_brackets_the_threshold():
    asked = bisect(threshold=1.0, comparator="<", fine_up_to=2.5)

    assert [(a.value, a.fine) for a in asked] == [(1.0, True), (3.0, False), (2.0, True)]
    resolution = resolve(asked, threshold=1.0, comparator="<")
    # Midway between the closest fine (2.0) and not-fine (3.0) Episodes, the margin their gap.
    assert (resolution.outcome, resolution.threshold, resolution.margin) == ("set", 2.5, 1.0)


def test_a_threshold_where_fine_is_high_bisects_the_other_way():
    asked = bisect(threshold=3.0, comparator=">=", fine_up_to=2.0)  # fine from 2.0 up

    assert [(a.value, a.fine) for a in asked] == [(3.0, True), (1.5, False), (2.5, True)]
    resolution = resolve(asked, threshold=3.0, comparator=">=")
    assert (resolution.outcome, resolution.threshold, resolution.margin) == ("set", 2.0, 1.0)


def test_answers_that_all_agree_with_the_threshold_confirm_it():
    asked = [Answered("droid_100:0", 0.5, True)]

    resolution = resolve(asked, threshold=1.0, comparator="<")

    assert (resolution.outcome, resolution.threshold, resolution.margin) == ("confirmed", 1.0, None)


def test_with_nothing_past_a_fine_answer_the_threshold_stays_unbracketed():
    # The curator finds even the farthest anchor Episode fine: no Episode brackets the line.
    asked = bisect(threshold=3.9, comparator="<", fine_up_to=10.0)

    assert [a.value for a in asked] == [4.0]
    assert resolve(asked, threshold=3.9, comparator="<").outcome == "unbracketed"


def test_equality_thresholds_are_never_bisected():
    assert next_point(POINTS, [], 1.0, "==") is None


def test_overlapping_answers_are_not_separated():
    # Review labels, unlike interview answers, can overlap: fine at 0.3 and 0.35 and not fine at
    # 0.6 leave no "≥" threshold that sorts them all.
    overlapping = [
        Answered("a", 0.3, True),
        Answered("b", 0.35, True),
        Answered("c", 0.6, False),
        Answered("d", 0.2, False),
    ]
    apart = [Answered("a", 0.3, True), Answered("d", 0.2, False)]

    assert not separated(overlapping, ">=")
    assert separated(apart, ">=")
    assert separated([Answered("a", 0.3, True)], ">=")  # one side only: nothing overlaps
