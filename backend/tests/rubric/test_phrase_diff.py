"""Which Phrases a Description edit leaves alone, and which changed text compile asks about."""

from winnow.rubric.diff import clarify_diff, diff_description
from winnow.rubric.models import DraftPhrase
from winnow.rubric.phrases import locate

OLD = "Tidy pick: one grasp only, never drops it, and no long pauses."


def phrases(description: str, *texts: str) -> list[DraftPhrase]:
    found: list[DraftPhrase] = []
    for text in texts:
        start, end = locate(description, text, [(p.start, p.end) for p in found])
        found.append(
            DraftPhrase(text=text, start=start, end=end, restatement=text, status="checked")
        )
    return found


DRAFT = phrases(OLD, "Tidy pick", "one grasp only", "never drops it", "no long pauses")


def kept_and_asked(new: str) -> tuple[list[str], list[str]]:
    diff = diff_description(OLD, DRAFT, new)
    for phrase in diff.kept:  # moved to where it sits now
        assert new[phrase.start : phrase.end] == phrase.text
    return [p.text for p in diff.kept], [s.text for s in diff.stretches]


def test_a_replaced_phrase_is_the_only_text_asked_about():
    new = "Tidy pick: one grasp only, never drops it, and pauses are fine."

    assert kept_and_asked(new) == (
        ["Tidy pick", "one grasp only", "never drops it"],
        ["pauses are fine"],
    )


def test_a_phrase_edited_inside_is_asked_about_whole():
    new = "Tidy pick: one grasp only, never drops it, and no pauses over 3 s."

    kept, asked = kept_and_asked(new)

    assert asked == ["no pauses over 3 s"]
    assert "no long pauses" not in kept


def test_words_added_at_a_phrase_edge_change_that_phrase():
    new = "Tidy pick: one grasp only, never drops it, and no long pauses while holding."

    assert kept_and_asked(new) == (
        ["Tidy pick", "one grasp only", "never drops it"],
        ["no long pauses while holding"],
    )


def test_a_new_sentence_is_asked_about_and_moves_the_phrases_after_it():
    new = "Careful. Tidy pick: one grasp only, never drops it, and no long pauses."

    assert kept_and_asked(new) == (
        ["Tidy pick", "one grasp only", "never drops it", "no long pauses"],
        ["Careful"],  # a sentence of its own, so it leaves the Phrase after it alone
    )


def test_a_deleted_phrase_asks_about_nothing():
    new = "Tidy pick: one grasp only, and no long pauses."

    assert kept_and_asked(new) == (["Tidy pick", "one grasp only", "no long pauses"], [])


def test_punctuation_and_filler_alone_ask_about_nothing():
    new = "Tidy pick: one grasp only; never drops it, no long pauses."

    assert kept_and_asked(new) == (
        ["Tidy pick", "one grasp only", "never drops it", "no long pauses"],
        [],
    )


def test_two_separate_edits_are_two_stretches():
    new = "Tidy pick: two grasps at most, never drops it, and pauses are fine."

    assert kept_and_asked(new) == (
        ["Tidy pick", "never drops it"],
        ["two grasps at most", "pauses are fine"],
    )


def test_changed_spacing_inside_a_phrase_changes_it():
    new = "Tidy pick: one grasp  only, never drops it, and no long pauses."

    kept, asked = kept_and_asked(new)

    assert asked == ["one grasp  only"]
    assert "one grasp only" not in kept


def kept_and_asked_from(old: str, texts: tuple[str, ...], new: str) -> tuple[list[str], list[str]]:
    diff = diff_description(old, phrases(old, *texts), new)
    for phrase in diff.kept:
        assert new[phrase.start : phrase.end] == phrase.text
    return [p.text for p in diff.kept], [s.text for s in diff.stretches]


def test_a_sentence_inserted_between_two_phrases_touches_neither():
    old = "Grasp once. No pauses."

    assert kept_and_asked_from(
        old, ("Grasp once", "No pauses"), "Grasp once. Move slowly. No pauses."
    ) == (["Grasp once", "No pauses"], ["Move slowly"])


def test_a_clause_appended_after_a_phrase_leaves_that_phrase_alone():
    new = "Tidy pick: one grasp only, never drops it, pauses are fine, and no long pauses."

    assert kept_and_asked(new) == (
        ["Tidy pick", "one grasp only", "never drops it", "no long pauses"],
        ["pauses are fine"],
    )


def test_a_clause_appended_to_a_phrase_at_the_end_leaves_it_alone():
    old = "Grasp once and never drops it"

    assert kept_and_asked_from(
        old, ("Grasp once", "never drops it"), "Grasp once and never drops it, pauses are fine"
    ) == (["Grasp once", "never drops it"], ["pauses are fine"])


def test_a_sentence_appended_to_a_description_with_no_final_period_is_asked_about_alone():
    old = "Grasp once. No pauses"

    assert kept_and_asked_from(
        old, ("Grasp once", "No pauses"), "Grasp once. No pauses. Move slowly."
    ) == (["Grasp once", "No pauses"], ["Move slowly"])


def test_a_word_added_right_after_a_phrase_changes_it():
    old = "No pauses."

    assert kept_and_asked_from(old, ("No pauses",), "No pauses ever.") == ([], ["No pauses ever"])


def test_a_word_added_inside_a_phrase_changes_it():
    old = "Tidy: No long pauses."

    assert kept_and_asked_from(old, ("Tidy", "No long pauses"), "Tidy: No very long pauses.") == (
        ["Tidy"],
        ["No very long pauses"],
    )


def test_clarifying_one_phrase_asks_about_it_alone_and_leaves_the_rest_where_it_is():
    never = DRAFT[2]

    diff = clarify_diff(OLD, DRAFT, never.start, never.end)

    assert [p.text for p in diff.kept] == ["Tidy pick", "one grasp only", "no long pauses"]
    assert [p.start for p in diff.kept] == [DRAFT[0].start, DRAFT[1].start, DRAFT[3].start]
    assert [s.text for s in diff.stretches] == ["never drops it"]
    assert diff.moved(never.start, never.end) is None  # its answers drop out
    assert diff.moved(DRAFT[3].start, DRAFT[3].end) == (DRAFT[3].start, DRAFT[3].end)
