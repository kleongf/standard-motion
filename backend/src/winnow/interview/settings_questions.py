"""The interview's questions after the Phrases and thresholds: whether each Criterion is hard or
soft, in Rubric order; then each assumed grasp setting, the gripper-closed level first (the
grasp rise is read at it), bisected on anchor Episodes' moments like a threshold."""

from collections.abc import Mapping, Sequence

from winnow.criteria.english import english
from winnow.criteria.models import Comparator
from winnow.interview.anchor import AnchorResult
from winnow.interview.apply import draft_setting
from winnow.interview.bisection import MAX_QUESTIONS, Point, next_point
from winnow.interview.models import (
    SETTING_NAMES,
    HardSoftQuestion,
    SettingName,
    SettingQuestion,
    StoredAnswer,
    hard_key,
    setting_key,
)
from winnow.interview.questions import asked_on
from winnow.interview.wording import (
    SETTING_WORDS,
    hard_soft_options,
    hard_soft_prompt,
    setting_options,
)
from winnow.rubric.models import RubricDraft

# Above the closed level the gripper is closed; rising at least the grasp rule is a lift.
SETTING_COMPARATORS: dict[SettingName, Comparator] = {
    "gripper_closed_level": ">",
    "grasp_rise_m": ">=",
}


def hard_soft_questions(
    draft: RubricDraft, answers: Sequence[StoredAnswer]
) -> list[HardSoftQuestion]:
    """One per Criterion switched on whose hardness no answer has confirmed, in Rubric order."""
    answered = {a.key for a in answers}
    return [
        HardSoftQuestion(
            key=hard_key(c.id),
            prompt=hard_soft_prompt(english(c)),
            options=hard_soft_options(c.hard),
            criterion_id=c.id,
            phrase=c.phrase,
            english=english(c),
            hard=c.hard,
        )
        for c in draft.criteria
        if c.id not in draft.disabled and hard_key(c.id) not in answered
    ]


def _setting_question(
    draft: RubricDraft,
    name: SettingName,
    points: Sequence[AnchorResult],
    answers: Sequence[StoredAnswer],
) -> SettingQuestion | None:
    setting = draft_setting(draft, name)
    asked = asked_on(answers, setting_key(name))
    candidates = [Point(p.episode_id, p.value) for p in points]
    point = next_point(candidates, asked, setting.value, SETTING_COMPARATORS[name])
    if setting.assumption is None or point is None:
        return None
    found = next(p for p in points if p.episode_id == point.episode_id)
    return SettingQuestion(
        key=setting_key(name),
        prompt=SETTING_WORDS[name].prompt,
        options=setting_options(name),
        setting=name,
        name=SETTING_WORDS[name].title,
        assumption=setting.assumption,
        episode_id=found.episode_id,
        value=found.value,
        measurement=found.measurement,
        camera=found.camera,
        clip=found.clip,
        asked=len(asked),
        max_questions=MAX_QUESTIONS,
    )


def setting_questions(
    draft: RubricDraft,
    points: Mapping[SettingName, Sequence[AnchorResult]],
    answers: Sequence[StoredAnswer],
) -> list[SettingQuestion]:
    """The next question on each assumed grasp setting still open, in the order they're asked."""
    closed = {a.key for a in answers if a.resolution is not None or a.answer == "skip"}
    questions: list[SettingQuestion] = []
    for name in SETTING_NAMES:
        if setting_key(name) in closed:
            continue
        question = _setting_question(draft, name, points.get(name, []), answers)
        if question is not None:
            questions.append(question)
    return questions
