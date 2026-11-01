"""The margin-multiplier scan over synthetic labelled (Episode, Phrase) pairs, and the
leave-one-out check: s ∈ {2, 1.5, 1, 0.75, 0.5}, widest first, keeping the last whose errors have
a one-sided Clopper–Pearson upper bound ≤ 0.2 at 90%."""

from winnow.calibration.scan import GRID, Pattern, scan, unstable


def pairs(n: int, first_wrong_at: dict[float, int]) -> list[Pattern]:
    """`n` labelled pairs, `first_wrong_at[s]` of them first contradicted at s and at every
    narrower s after it (a narrower margin leaves fewer results unsure); the rest never are."""
    made: list[Pattern] = []
    for s, count in first_wrong_at.items():
        start = GRID.index(s)
        made += [tuple(i >= start for i in range(len(GRID)))] * count
    return made + [(False,) * len(GRID)] * (n - len(made))


def test_the_grid_is_scanned_widest_first():
    assert GRID == (2.0, 1.5, 1.0, 0.75, 0.5)


def test_the_scan_keeps_the_last_s_whose_upper_bound_is_at_most_0_2():
    # 30 pairs; errors by s: 0, 1, 2, 3, 5. Upper bounds 0.074, 0.124, 0.168, 0.209: 0.75 fails.
    labelled = pairs(30, {1.5: 1, 1.0: 1, 0.75: 1, 0.5: 2})

    result = scan(labelled)

    assert (result.s, result.bound_met, result.n, result.errors) == (1.0, True, 30, 2)


def test_every_s_passing_keeps_the_narrowest():
    result = scan(pairs(30, {}))

    assert (result.s, result.bound_met, result.errors) == (0.5, True, 0)


def test_when_even_the_widest_s_misses_the_bound_s_stays_at_2_and_says_so():
    # 10 pairs with none wrong is already 0.206: too few labels for any s.
    result = scan(pairs(10, {}))

    assert (result.s, result.bound_met, result.errors) == (2.0, False, 0)


def test_unsure_is_not_an_error_so_only_contradicted_pairs_count():
    # A pair unsure at every s is never wrong, but still one of n.
    result = scan([(False,) * 5] * 12)

    assert (result.n, result.errors, result.s) == (12, 0, 0.5)


def test_dropping_two_labels_that_move_s_marks_the_margins_unstable():
    # As above, s = 1. Dropping the two pairs first wrong at 1 and 0.75 leaves errors 0, 1, 1,
    # 1, 3 of 28, so 0.75 passes (0.132) and 0.5 fails (0.223): s moves to 0.75.
    assert unstable(pairs(30, {1.5: 1, 1.0: 1, 0.75: 1, 0.5: 2}))


def test_a_scan_no_two_labels_can_move_is_stable():
    # 60 pairs, s = 1: half are wrong at 0.75, far past the bound whichever two are dropped,
    # and 1 passes with none wrong.
    assert not unstable(pairs(60, {0.75: 30}))


def test_too_few_labels_to_drop_two_is_stable():
    assert not unstable(pairs(1, {}))
    assert not unstable([])
