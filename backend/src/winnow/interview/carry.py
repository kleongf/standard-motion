"""Which interview answers still hold after a recompile, which edits only part of the Description.

An answer about a Phrase, or words in no Phrase, that the edit left alone still holds, moved to
where its text now sits; so does a Phrase's answer on an Episode its Criteria disagree on, and
every answer on a threshold, or on whether a Criterion is hard, of a Criterion whose Phrase was
kept, so a bisection goes on where it was. Answers on the grasp settings, which an edit never
changes, always hold. Answers about text the edit changed or took out drop out of the interview:
their questions are asked again, of the new text. Pure: the caller saves what it returns.
"""

from winnow.interview.models import StoredAnswer
from winnow.rubric.diff import DescriptionDiff
from winnow.rubric.models import RubricDraft


def _on_kept_criterion(answer: StoredAnswer, draft: RubricDraft, kept: set[str]) -> bool:
    """Whether the Criterion a threshold or hard/soft answer is about (its key's
    `<kind>:<criterion id>`) is still in the draft, on a kept Phrase."""
    criterion_id = answer.key.partition(":")[2]
    return any(c.id == criterion_id and c.phrase in kept for c in draft.criteria)


def _moved(answer: StoredAnswer, diff: DescriptionDiff) -> StoredAnswer | None:
    """An answer keyed by where its Phrase or words start (`<kind>:<start>`), moved with its text;
    None when the edit touched that text."""
    start = int(answer.key.removeprefix(f"{answer.kind}:"))
    now = diff.moved(start, start + len(answer.subject))
    if now is None:
        return None
    shift = now[0] - start
    before = answer.phrase_before
    return answer.model_copy(
        update={
            "key": f"{answer.kind}:{now[0]}",
            "context_at": None if answer.context_at is None else answer.context_at + shift,
            "phrase_before": before
            and before.model_copy(
                update={"start": before.start + shift, "end": before.end + shift}
            ),
        }
    )


def carried(
    answers: list[StoredAnswer], diff: DescriptionDiff, draft: RubricDraft
) -> list[StoredAnswer]:
    """`answers` are the interview's on the draft `diff` starts from; `draft` is the recompiled
    one. Returns those that still hold, in their order."""
    kept = {p.text for p in diff.kept}
    still: list[StoredAnswer] = []
    for answer in answers:
        if answer.kind == "setting":
            moved = answer
        elif answer.kind in ("threshold", "hard_soft"):
            moved = answer if _on_kept_criterion(answer, draft, kept) else None
        else:  # "phrase", "words" and "disagree": keyed by where their text starts
            moved = _moved(answer, diff)
        if moved is not None:
            still.append(moved)
    return still
