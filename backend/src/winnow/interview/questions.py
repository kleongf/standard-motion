"""Which question code asks next, from the draft, the anchor pool and the answers so far.

Order: Unsupported Phrases and runs of meaningful words in no Phrase, in Description order; then
assumed thresholds, a threshold already being bisected first, the rest ranked by how many
anchor Episodes sit within their margin (ties in Rubric order).
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from winnow.criteria.english import english
from winnow.criteria.models import Criterion
from winnow.interview.anchor import AnchorResult
from winnow.interview.bisection import MAX_QUESTIONS, Answered, Point, next_point
from winnow.interview.models import PhraseQuestion, StoredAnswer, ThresholdQuestion
from winnow.interview.wording import (
    PHRASE_OPTIONS,
    phrase_prompt,
    threshold_options,
    threshold_prompt,
    words_prompt,
)
from winnow.rubric.models import RubricDraft
from winnow.triage.confidence import effective_margin

# Punctuation that ends a clause: uncovered words either side of it are separate questions.
CLAUSE_END = re.compile(r"[,.;:!?]")


def threshold_key(criterion_id: str) -> str:
    return f"threshold:{criterion_id}"


def _runs(draft: RubricDraft) -> list[tuple[int, int]]:
    """Uncovered words grouped into runs, split at Phrases and clause punctuation."""
    runs: list[tuple[int, int]] = []
    for word in draft.uncovered:
        if runs:
            start, end = runs[-1]
            between = draft.description[end : word.start]
            split = CLAUSE_END.search(between) or any(
                end <= p.start and p.end <= word.start for p in draft.phrases
            )
            if not split:
                runs[-1] = (start, word.end)
                continue
        runs.append((word.start, word.end))
    return runs


def phrase_questions(draft: RubricDraft, answered: set[str]) -> list[PhraseQuestion]:
    """Unsupported Phrases and uncovered words not yet answered, in Description order."""
    questions = [
        PhraseQuestion(
            kind="phrase",
            key=f"phrase:{p.start}",
            prompt=phrase_prompt(p.text, p.reason),
            options=PHRASE_OPTIONS,
            text=p.text,
            start=p.start,
            end=p.end,
            reason=p.reason,
        )
        for p in draft.phrases
        if p.status == "unsupported"
    ]
    for start, end in _runs(draft):
        text = draft.description[start:end]
        questions.append(
            PhraseQuestion(
                kind="words",
                key=f"words:{start}",
                prompt=words_prompt(text),
                options=PHRASE_OPTIONS,
                text=text,
                start=start,
                end=end,
                reason=None,
            )
        )
    return sorted((q for q in questions if q.key not in answered), key=lambda q: q.start)


def asked_on(answers: Sequence[StoredAnswer], key: str) -> list[Answered]:
    """A threshold's pass/fail answers so far, as bisection reads them."""
    return [
        Answered(a.episode_id, a.value, a.answer == "pass")
        for a in answers
        if a.key == key and a.episode_id is not None and a.value is not None
    ]


@dataclass(frozen=True)
class _Candidate:
    criterion: Criterion
    results: list[AnchorResult]
    near: int


def _candidates(
    draft: RubricDraft, anchor: dict[str, list[AnchorResult]], closed: set[str]
) -> list[_Candidate]:
    found: list[_Candidate] = []
    for c in draft.criteria:
        results = anchor.get(c.id, [])
        askable = c.kind != "visual" and c.comparator != "=="
        if not (askable and c.assumptions and results and c.id not in draft.disabled):
            continue
        if threshold_key(c.id) in closed:
            continue
        margin = effective_margin(c)
        near = sum(1 for r in results if abs(r.value - c.threshold) < margin)
        found.append(_Candidate(c, results, near))
    return found


def _ranked(candidates: list[_Candidate], open_keys: set[str]) -> list[_Candidate]:
    """The threshold being bisected first, then most anchor Episodes near; stable otherwise."""
    return sorted(
        candidates,
        key=lambda x: (threshold_key(x.criterion.id) not in open_keys, -x.near),
    )


def _question(candidate: _Candidate, asked: list[Answered]) -> ThresholdQuestion | None:
    c = candidate.criterion
    points = [Point(r.episode_id, r.value) for r in candidate.results]
    point = next_point(points, asked, c.threshold, c.comparator)
    if point is None:
        return None
    result = next(r for r in candidate.results if r.episode_id == point.episode_id)
    return ThresholdQuestion(
        key=threshold_key(c.id),
        prompt=threshold_prompt(result.measurement, c.phrase),
        options=threshold_options(c.phrase),
        criterion_id=c.id,
        phrase=c.phrase,
        english=english(c),
        episode_id=result.episode_id,
        value=result.value,
        measurement=result.measurement,
        camera=result.camera,
        clip=result.clip,
        asked=len(asked),
        max_questions=MAX_QUESTIONS,
        near=candidate.near,
    )


def threshold_questions(
    draft: RubricDraft,
    anchor: dict[str, list[AnchorResult]],
    answers: Sequence[StoredAnswer],
) -> list[ThresholdQuestion]:
    """The next question on each assumed threshold still open, in the order they're asked."""
    closed = {a.key for a in answers if a.resolution is not None or a.answer == "skip"}
    open_keys = {a.key for a in answers} - closed
    questions: list[ThresholdQuestion] = []
    for candidate in _ranked(_candidates(draft, anchor, closed), open_keys):
        asked = asked_on(answers, threshold_key(candidate.criterion.id))
        question = _question(candidate, asked)
        if question is not None:
            questions.append(question)
    return questions
