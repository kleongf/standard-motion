"""What a hard/soft or grasp-setting answer changes in the Rubric draft. Pure: each returns the
answer as kept and the changed draft (None when it changes nothing), which the service saves.
Neither leaves a label: neither judges an Episode on a Phrase."""

from collections.abc import Sequence

from winnow.interview.anchor import AnchorResult
from winnow.interview.apply import criterion, draft_setting, set_hard, settle_setting
from winnow.interview.bisection import Answered, Point, next_point, resolve
from winnow.interview.models import (
    AnswerValue,
    HardSoftQuestion,
    SettingQuestion,
    StoredAnswer,
)
from winnow.interview.questions import asked_on
from winnow.interview.settings_questions import SETTING_COMPARATORS
from winnow.interview.wording import hard_soft_effect, setting_answer_effect, setting_effect
from winnow.rubric.models import RubricDraft


def answer_hard_soft(
    draft: RubricDraft, q: HardSoftQuestion, answer: AnswerValue
) -> tuple[StoredAnswer, RubricDraft | None]:
    stored = StoredAnswer.unchanged(
        q.key, "hard_soft", q.english, answer, hard_soft_effect(answer, q.hard)
    )
    if answer == "skip":
        return stored, None
    found = criterion(draft, q.criterion_id)
    stored = stored.model_copy(update={"changed_criterion": found.id, "criterion_before": found})
    return stored, set_hard(draft, found.id, answer == "hard")


def answer_setting(
    draft: RubricDraft,
    answers: Sequence[StoredAnswer],
    points: Sequence[AnchorResult],
    q: SettingQuestion,
    answer: AnswerValue,
) -> tuple[StoredAnswer, RubricDraft | None]:
    """One step of bisecting the setting; the answer that settles it changes the draft."""
    effect = setting_answer_effect(q.setting, q.episode_id, answer)
    stored = StoredAnswer.unchanged(q.key, "setting", q.name, answer, effect)
    if answer == "skip":
        return stored, None
    stored = stored.model_copy(
        update={"episode_id": q.episode_id, "measurement": q.measurement, "value": q.value}
    )
    asked = [*asked_on(answers, q.key), Answered(q.episode_id, q.value, answer == "pass")]
    before = draft_setting(draft, q.setting)
    comparator = SETTING_COMPARATORS[q.setting]
    candidates = [Point(p.episode_id, p.value) for p in points]
    if next_point(candidates, asked, before.value, comparator) is not None:
        return stored, None  # bisection goes on
    resolution = resolve(asked, before.value, comparator)
    settled = stored.model_copy(
        update={
            "effect": f"{effect} {setting_effect(q.setting, resolution, before)}",
            "resolution": resolution.outcome,
            "setting_before": before,
        }
    )
    return settled, settle_setting(draft, q.setting, resolution)
