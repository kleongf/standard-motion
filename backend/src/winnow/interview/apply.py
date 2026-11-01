"""What interview answers change in the Rubric draft, and how undo puts it back. Pure: the service
saves the result."""

from collections.abc import Set

from winnow.criteria.models import Criterion, Setting
from winnow.interview.bisection import Resolution
from winnow.interview.models import SettingName, StoredAnswer, setting_of
from winnow.rubric.models import DraftPhrase, RubricDraft

CONTEXT_REASON = "Marked Context in the interview."
# What settling a threshold changes, and so what undoing it puts back.
SETTLED = frozenset({"threshold", "margin", "assumptions"})


def mark_context(draft: RubricDraft, start: int, end: int) -> RubricDraft:
    """The Phrase at `start` becomes Context; words in no Phrase become a Context Phrase."""
    text = draft.description[start:end]
    others = [p for p in draft.phrases if p.start != start]
    phrase = DraftPhrase(
        text=text,
        start=start,
        end=end,
        restatement=next(
            (p.restatement for p in draft.phrases if p.start == start), f"Context: {text}."
        ),
        status="context",
        reason=CONTEXT_REASON,
    )
    return draft.model_copy(update={"phrases": sorted([*others, phrase], key=lambda p: p.start)})


def criterion(draft: RubricDraft, criterion_id: str) -> Criterion:
    return next(c for c in draft.criteria if c.id == criterion_id)


def _replace(draft: RubricDraft, changed: Criterion) -> RubricDraft:
    return draft.model_copy(
        update={"criteria": [changed if c.id == changed.id else c for c in draft.criteria]}
    )


def settle(draft: RubricDraft, criterion_id: str, resolution: Resolution) -> RubricDraft:
    """A bracketed threshold moves and takes its margin; a confirmed one keeps both. Either way
    its value is no longer an assumption. An unbracketed one stays as it is."""
    if resolution.outcome == "unbracketed":
        return draft
    found = criterion(draft, criterion_id)
    changes: dict[str, object] = {"assumptions": []}
    if resolution.outcome == "set":
        changes |= {"threshold": resolution.threshold, "margin": resolution.margin}
    return _replace(draft, found.model_copy(update=changes))


def set_hard(draft: RubricDraft, criterion_id: str, hard: bool) -> RubricDraft:
    return _replace(draft, criterion(draft, criterion_id).model_copy(update={"hard": hard}))


def restore_criterion(
    draft: RubricDraft, before: Criterion, fields: Set[str] = SETTLED
) -> RubricDraft:
    """Puts back what an answer changed (`fields` of the Criterion), keeping later edits."""
    current = next((c for c in draft.criteria if c.id == before.id), None)
    if current is None:
        return draft
    return _replace(draft, current.model_copy(update=before.model_dump(include=set(fields))))


def draft_setting(draft: RubricDraft, name: SettingName) -> Setting:
    settings = draft.settings
    return (
        settings.gripper_closed_level if name == "gripper_closed_level" else settings.grasp_rise_m
    )


def _with_setting(draft: RubricDraft, name: SettingName, changed: Setting) -> RubricDraft:
    settings = draft.settings.model_copy(update={name: changed})
    return draft.model_copy(update={"settings": settings})


def settle_setting(draft: RubricDraft, name: SettingName, resolution: Resolution) -> RubricDraft:
    """As `settle`, for a grasp setting: its value is no longer an assumption."""
    if resolution.outcome == "unbracketed":
        return draft
    changes: dict[str, object] = {"assumption": None}
    if resolution.outcome == "set":
        changes |= {"value": resolution.threshold, "margin": resolution.margin}
    return _with_setting(draft, name, draft_setting(draft, name).model_copy(update=changes))


def undone(draft: RubricDraft, answer: StoredAnswer) -> RubricDraft:
    """The draft with what `answer` changed put back, and only that, so later answers and direct
    edits to anything else stand."""
    if answer.criterion_before is not None:
        fields = {"hard"} if answer.kind == "hard_soft" else SETTLED
        draft = restore_criterion(draft, answer.criterion_before, fields)
    if answer.setting_before is not None:
        draft = _with_setting(draft, setting_of(answer.key), answer.setting_before)
    if answer.context_at is not None:
        draft = restore_phrase(draft, answer.context_at, answer.phrase_before)
    return draft


def restore_phrase(draft: RubricDraft, start: int, before: DraftPhrase | None) -> RubricDraft:
    """Puts back the Phrase made Context at `start`: as it was, or gone when it was words in no
    Phrase. Every other Phrase stays as it is now."""
    others = [p for p in draft.phrases if p.start != start]
    phrases = others if before is None else sorted([*others, before], key=lambda p: p.start)
    return draft.model_copy(update={"phrases": phrases})
