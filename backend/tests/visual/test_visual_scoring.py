"""Visual Criteria in the pure scoring function: Spark's three answers, one per frozen
paraphrase, become a Criterion result, an Uncertainty signal and a p."""

from dataclasses import replace

import pytest

from tests.triage.robot_data import CLEAN_GRIPPER, CLEAN_Z, PLACES, SETTINGS, facts, rubric, text
from tests.visual.answers import answers, placed
from winnow.criteria.facts import EpisodeFacts
from winnow.triage.scoring import score
from winnow.visual.keys import ask_key
from winnow.visual.models import AnswerValue, VisualAnswers


def with_answers(found: VisualAnswers | None) -> EpisodeFacts:
    base = facts(CLEAN_GRIPPER, CLEAN_Z)
    if found is None:
        return base
    return replace(base, visual={ask_key(placed(), SETTINGS): found})


def test_three_passing_samples_pass_conclusively_and_keep():
    triage = score(rubric(placed()), with_answers(answers("pass", "pass", "pass")))

    [result] = triage.criteria
    assert (result.kind, result.status, result.uncertainty) == ("visual", "pass", None)
    assert result.measurement == "3 pass"
    assert result.p_pass == pytest.approx(0.8, abs=0.02)  # (3 + 1) / (3 + 2)
    assert triage.decision == "keep"


def test_a_two_one_split_is_unsure_with_samples_split():
    triage = score(rubric(placed()), with_answers(answers("pass", "fail", "pass")))

    [result] = triage.criteria
    assert (result.status, result.uncertainty) == ("unsure", "samples split")
    assert result.measurement == "2 pass · 1 fail"
    assert result.p_pass == pytest.approx(0.6, abs=0.02)  # (2 + 1) / (3 + 2)
    assert triage.decision == "needs_review"
    assert text(triage) == f'Needs review: "{PLACES}": samples split (2 pass · 1 fail).'


@pytest.mark.parametrize(
    "values", [("pass", "pass", "unsure"), ("fail", "unsure", "fail"), ("unsure",) * 3]
)
def test_any_sample_answering_unsure_makes_it_unsure(values: tuple[AnswerValue, ...]):
    [result] = score(rubric(placed()), with_answers(answers(*values))).criteria

    assert (result.status, result.uncertainty) == ("unsure", "Spark said unsure")


def test_three_failing_samples_fail_conclusively_and_reject_from_the_clip():
    triage = score(rubric(placed()), with_answers(answers("fail", "fail", "fail")))

    [result] = triage.criteria
    assert (result.status, result.measurement) == ("fail", "3 fail")
    assert result.p_pass == pytest.approx(0.2, abs=0.02)
    assert result.window is not None and result.at_s == result.window.start
    assert triage.decision == "reject"
    assert text(triage) == (
        f'Rejected: "{PLACES}" failed. All 3 samples: fail. Saw 0. Asked of the whole view: no '
        "object track and target box to crop to."
    )


def test_stated_confidence_breaks_ties_but_never_crosses_a_tally():
    def p(*values: AnswerValue, confidence: float) -> float:
        found = answers(*values, confidence=confidence)
        return score(rubric(placed()), with_answers(found)).criteria[0].p_pass

    assert p("pass", "pass", "pass", confidence=0.9) > p("pass", "pass", "pass", confidence=0.5)
    assert p("pass", "fail", "pass", confidence=0.9) > p("pass", "fail", "pass", confidence=0.3)
    assert p("pass", "pass", "pass", confidence=0.0) > p("pass", "fail", "pass", confidence=1.0)


def test_before_spark_is_asked_the_result_is_unsure_with_source_missing():
    triage = score(rubric(placed()), with_answers(None))

    [result] = triage.criteria
    assert (result.status, result.uncertainty, result.value) == ("unsure", "source missing", None)
    assert result.p_pass == 0.5
    assert triage.decision == "needs_review"


def test_a_clip_cut_but_not_yet_asked_about_is_still_unasked():
    cut = answers("pass", "pass", "pass").model_copy(update={"samples": []})

    [result] = score(rubric(placed()), with_answers(cut)).criteria

    assert (result.status, result.uncertainty) == ("unsure", "source missing")


def test_a_failed_step_is_unsure_with_its_error_as_evidence():
    failed = answers("pass", "pass", "pass").model_copy(
        update={"clip": None, "samples": [], "error": "ffmpeg failed: no such clip"}
    )

    [result] = score(rubric(placed()), with_answers(failed)).criteria

    assert (result.status, result.uncertainty) == ("unsure", "step failed")
    assert "ffmpeg failed: no such clip" in result.evidence[0].text


def test_a_malformed_sample_leaves_too_few_answers_to_agree():
    found = answers("pass", "pass", "pass")
    found.samples[1] = found.samples[1].model_copy(
        update={"reply": None, "error": "malformed answer"}
    )

    [result] = score(rubric(placed()), with_answers(found)).criteria

    assert (result.status, result.uncertainty) == ("unsure", "step failed")


def test_each_samples_answer_and_the_clip_are_its_evidence():
    [result] = score(rubric(placed()), with_answers(answers("pass", "fail", "pass"))).criteria

    assert result.visual is not None
    assert [s.reply.answer for s in result.visual.samples if s.reply] == ["pass", "fail", "pass"]
    assert [s.prompt for s in result.visual.samples] == [placed().question, *placed().paraphrases]
    assert result.visual.clip is not None and result.visual.clip.name.endswith(".mp4")
    assert result.camera == "exterior_image_1_left"


def test_a_placement_question_asked_of_the_whole_view_says_so():
    # CLIP has no crop box: the Episode had no object track and target box to crop to.
    [result] = score(rubric(placed()), with_answers(answers("pass", "pass", "pass"))).criteria

    assert "whole view" in "".join(s.text for s in result.evidence)


def test_a_soft_visual_criterion_never_changes_the_decision():
    triage = score(rubric(placed(hard=False)), with_answers(answers("fail", "fail", "fail")))

    assert triage.criteria[0].status == "fail"
    assert triage.decision == "keep"
