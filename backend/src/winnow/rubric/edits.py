"""Direct edits to the Rubric draft: a threshold, hard or soft, on or off, and the two Rubric
settings. Pure, with no model call, so the preview can apply one without saving it."""

from winnow.criteria.models import Criterion, RubricSettings, Setting
from winnow.rubric.models import CriterionEdit, DraftEdit, RubricDraft


class UnknownCriterionError(ValueError):
    pass


def _criterion(criterion: Criterion, edit: CriterionEdit) -> Criterion:
    changes: dict[str, object] = {}
    if edit.threshold is not None:
        changes["threshold"] = edit.threshold
    if edit.hard is not None:
        changes["hard"] = edit.hard
    return criterion.model_copy(update=changes)


def _confirmed(setting: Setting, value: float | None) -> Setting:
    if value is None:
        return setting
    return setting.model_copy(update={"value": value, "assumption": None})


def _settings(settings: RubricSettings, edit: DraftEdit) -> RubricSettings:
    return RubricSettings(
        gripper_closed_level=_confirmed(settings.gripper_closed_level, edit.gripper_closed_level),
        grasp_rise_m=_confirmed(settings.grasp_rise_m, edit.grasp_rise_m),
    )


def _disabled(draft: RubricDraft, edit: DraftEdit) -> list[str]:
    switched = {id_: e.enabled for id_, e in edit.criteria.items() if e.enabled is not None}
    return [c.id for c in draft.criteria if not switched.get(c.id, c.id not in draft.disabled)]


def apply_edit(draft: RubricDraft, edit: DraftEdit) -> RubricDraft:
    unknown = set(edit.criteria) - {c.id for c in draft.criteria}
    if unknown:
        raise UnknownCriterionError(f"The draft has no Criterion {', '.join(sorted(unknown))}")
    return draft.model_copy(
        update={
            "criteria": [
                _criterion(c, edit.criteria.get(c.id, CriterionEdit())) for c in draft.criteria
            ],
            "settings": _settings(draft.settings, edit),
            "disabled": _disabled(draft, edit),
        }
    )
