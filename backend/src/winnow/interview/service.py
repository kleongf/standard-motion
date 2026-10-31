"""The Describe interview on the Rubric draft: code picks each question, an answer changes the
draft and may leave an interview label, and undo puts both back. No model call here: only an
answer in the curator's own words asks Spark (`interview.text`), and what it maps to an offered
answer is applied here like a picked one."""

from dataclasses import dataclass

from winnow.core.context import AppContext
from winnow.interview.anchor import (
    AnchorResult,
    AnchorTriage,
    anchor_results,
    anchor_setting_points,
    anchor_triage,
)
from winnow.interview.apply import criterion, mark_context, settle, undone
from winnow.interview.bisection import Answered, Point, next_point, resolve
from winnow.interview.disagree import disagree_questions
from winnow.interview.models import (
    AnswerDraw,
    AnswerValue,
    DisagreeQuestion,
    HardSoftQuestion,
    Interview,
    PhraseQuestion,
    Question,
    SettingName,
    SettingQuestion,
    StoredAnswer,
    ThresholdQuestion,
    asked_episode,
)
from winnow.interview.questions import asked_on, phrase_questions, threshold_questions
from winnow.interview.settings_answers import answer_hard_soft, answer_setting
from winnow.interview.settings_questions import hard_soft_questions, setting_questions
from winnow.interview.wording import (
    DISAGREE_SKIPPED,
    label_effect,
    phrase_effect,
    resolution_effect,
)
from winnow.labels.models import LabelDraw
from winnow.labels.service import save_draft_label
from winnow.rubric.models import RubricDraft
from winnow.rubric.service import current_draft


class StaleQuestionError(ValueError):
    """The answer isn't to the question code is asking now."""


class UnknownAnswerError(LookupError):
    pass


@dataclass(frozen=True)
class _State:
    draft: RubricDraft
    answers: list[StoredAnswer]
    anchor: dict[str, list[AnchorResult]]  # by Criterion id
    moments: dict[SettingName, list[AnchorResult]]  # by grasp setting
    phrases: list[PhraseQuestion]
    thresholds: list[ThresholdQuestion]
    hard_soft: list[HardSoftQuestion]
    settings: list[SettingQuestion]
    disagree: list[DisagreeQuestion]

    @property
    def asking(self) -> Question | None:
        """In order: Phrases, thresholds, hard or soft, grasp settings, Criteria that disagree."""
        asked = [
            *self.phrases,
            *self.thresholds,
            *self.hard_soft,
            *self.settings,
            *self.disagree,
        ]
        return next(iter(asked), None)


def _labelled_pairs(ctx: AppContext, triaged: list[AnchorTriage]) -> set[tuple[str, str]]:
    """The (Episode id, Phrase) pairs of the anchor pool with a label in force."""
    return {
        (e.episode_id, label.phrase) for e in triaged for label in ctx.labels.in_force(e.episode_id)
    }


def _state(ctx: AppContext) -> _State:
    """The draft scored on the anchor pool once, and every question still open."""
    draft = current_draft(ctx)
    answers = ctx.interview.answers(draft.compiled_at)
    triaged = anchor_triage(ctx, draft)
    anchor = anchor_results(draft, triaged)
    moments = anchor_setting_points(ctx, draft.settings)
    return _State(
        draft,
        answers,
        anchor,
        moments,
        phrase_questions(draft, {a.key for a in answers}),
        threshold_questions(draft, anchor, answers),
        hard_soft_questions(draft, answers),
        setting_questions(draft, moments, answers),
        disagree_questions(draft, triaged, _labelled_pairs(ctx, triaged), answers),
    )


def current(ctx: AppContext) -> Interview:
    state = _state(ctx)
    return Interview(
        answered=list(state.answers),
        question=state.asking,
        covered=not state.phrases,
        phrases_left=len(state.phrases),
        thresholds_left=len(state.thresholds),
        hard_soft_left=len(state.hard_soft),
        settings_left=len(state.settings),
        disagree_left=len(state.disagree),
    )


def _answer_phrase(
    ctx: AppContext, draft: RubricDraft, q: PhraseQuestion, value: AnswerValue
) -> StoredAnswer:
    stored = StoredAnswer.unchanged(q.key, q.kind, q.text, value, phrase_effect(value, q.text))
    if value != "context":
        return stored
    ctx.drafts.save(mark_context(draft, q.start, q.end))
    before = next((p for p in draft.phrases if p.start == q.start), None)
    return stored.model_copy(update={"context_at": q.start, "phrase_before": before})


def _label_answer(
    ctx: AppContext, q: ThresholdQuestion | DisagreeQuestion, answer: AnswerValue
) -> StoredAnswer:
    """A pass or fail answer on an anchor Episode, saved as an interview label on the Phrase."""
    value = "pass" if answer == "pass" else "fail"
    label = save_draft_label(
        ctx, q.episode_id, LabelDraw(phrase=q.phrase, value=value, source="interview")
    )
    stored = StoredAnswer.unchanged(
        q.key, q.kind, q.phrase, answer, label_effect(q.episode_id, value, q.phrase)
    )
    update = {"episode_id": q.episode_id, "measurement": q.measurement, "label_id": label.id}
    return stored.model_copy(update=update)


def _answer_threshold(
    ctx: AppContext, state: _State, q: ThresholdQuestion, answer: AnswerValue
) -> StoredAnswer:
    if answer == "skip":
        return StoredAnswer.unchanged(
            q.key, "threshold", q.phrase, answer, "Skipped: the threshold stays assumed."
        )
    stored = _label_answer(ctx, q, answer).model_copy(update={"value": q.value})
    asked = [*asked_on(state.answers, q.key), Answered(q.episode_id, q.value, answer == "pass")]
    found = criterion(state.draft, q.criterion_id)
    points = [Point(r.episode_id, r.value) for r in state.anchor[found.id]]
    if next_point(points, asked, found.threshold, found.comparator) is not None:
        return stored  # bisection goes on
    resolution = resolve(asked, found.threshold, found.comparator)
    ctx.drafts.save(settle(state.draft, found.id, resolution))
    changed = resolution.outcome != "unbracketed"
    return stored.model_copy(
        update={
            "effect": f"{stored.effect} {resolution_effect(resolution, found)}",
            "changed_criterion": found.id if changed else None,
            "resolution": resolution.outcome,
            "criterion_before": found,
        }
    )


def _answer_disagree(ctx: AppContext, q: DisagreeQuestion, answer: AnswerValue) -> StoredAnswer:
    if answer == "skip":
        return StoredAnswer.unchanged(q.key, "disagree", q.phrase, answer, DISAGREE_SKIPPED)
    return _label_answer(ctx, q, answer)


def _asked(state: _State, draw: AnswerDraw) -> Question:
    """The question being asked, which `draw` must answer with one of its options."""
    asking = state.asking
    if asking is None or asking.key != draw.key:
        raise StaleQuestionError("That question isn't the one being asked")
    if draw.answer not in {o.answer for o in asking.options}:
        raise StaleQuestionError(f"“{draw.answer}” doesn't answer this question")
    episode = asked_episode(asking)
    if episode is not None and draw.episode_id != episode:
        raise StaleQuestionError(f"The question is about {episode} now")
    return asking


def _changed(ctx: AppContext, answered: tuple[StoredAnswer, RubricDraft | None]) -> StoredAnswer:
    """Saves the draft an answer changed, if it did."""
    stored, draft = answered
    if draft is not None:
        ctx.drafts.save(draft)
    return stored


def answer(ctx: AppContext, draw: AnswerDraw) -> Interview:
    """Raises StaleQuestionError unless `draw` answers the question being asked, with one of
    its options."""
    state = _state(ctx)
    value = draw.answer
    match _asked(state, draw):
        case PhraseQuestion() as q:
            stored = _answer_phrase(ctx, state.draft, q, value)
        case ThresholdQuestion() as q:
            stored = _answer_threshold(ctx, state, q, value)
        case HardSoftQuestion() as q:
            stored = _changed(ctx, answer_hard_soft(state.draft, q, value))
        case SettingQuestion() as q:
            moments = state.moments[q.setting]
            stored = _changed(ctx, answer_setting(state.draft, state.answers, moments, q, value))
        case DisagreeQuestion() as q:
            stored = _answer_disagree(ctx, q, value)
    ctx.interview.add(state.draft.compiled_at, stored)
    return current(ctx)


def undo(ctx: AppContext, answer_id: int) -> Interview:
    """Undoes an answer and every later one on the same question: the draft gets back what they
    changed, and their labels are withdrawn."""
    draft = current_draft(ctx)
    answers = ctx.interview.answers(draft.compiled_at)
    target = next((a for a in answers if a.id == answer_id), None)
    if target is None:
        raise UnknownAnswerError(f"No answer {answer_id} in this interview")
    later = [a for a in answers if a.key == target.key and a.id >= target.id]
    for a in reversed(later):
        draft = undone(draft, a)
        if a.label_id is not None:
            ctx.labels.withdraw(a.label_id)
    ctx.drafts.save(draft)
    ctx.interview.remove([a.id for a in later])
    return current(ctx)
