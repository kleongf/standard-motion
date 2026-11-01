"""Compile: one contributor Spark call turns a Description into a Rubric draft. A recompile
(`rubric.recompile`) asks the same way about only the text an edit changed.

Every Phrase in the answer goes through code's checks (`rubric.answer`). Those that fail get one
repair turn; a Phrase that still fails becomes Unsupported with the error as its reason, or, when
it isn't even in the Description, is rejected and listed.
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from winnow.criteria.models import Criterion, RubricSettings
from winnow.meta.client import MetaClient
from winnow.meta.models import SparkRequest, Text
from winnow.meta.pricing import SPARK_CONTRIBUTOR
from winnow.rubric.answer import (
    AnswerPhrase,
    CheckedPhrase,
    PhraseError,
    answer_schema,
    check_phrase,
    parse_answer,
)
from winnow.rubric.models import DraftPhrase, RejectedPhrase, RubricDraft
from winnow.rubric.phrases import locate
from winnow.rubric.prompt import compile_prompt, repair_prompt

MAX_OUTPUT_TOKENS = 16000  # effort `high` reasons at length before a long structured answer


class CompileError(RuntimeError):
    """Spark's answer couldn't be read even after the repair turn."""


@dataclass(frozen=True)
class Failure:
    answer: AnswerPhrase
    error: str


@dataclass(frozen=True)
class Scope:
    """The Description being compiled, and the spans of Phrases a recompile keeps, which no new
    Phrase may overlap."""

    description: str
    kept: tuple[tuple[int, int], ...] = ()

    def check(self, answers: list[AnswerPhrase], accepted: list[CheckedPhrase]) -> list[Failure]:
        """Appends each answer that passes to `accepted`; returns the rest with their errors."""
        failures: list[Failure] = []
        for answer in answers:
            taken = [*self.kept, *((c.phrase.start, c.phrase.end) for c in accepted)]
            try:
                accepted.append(check_phrase(answer, self.description, taken))
            except PhraseError as error:
                failures.append(Failure(answer, str(error)))
        return failures


@dataclass(frozen=True)
class Compiled:
    """What one compile call, with its repair turn, made of the text it asked about."""

    accepted: list[CheckedPhrase]
    failures: list[Failure]  # still failing after the repair turn


async def _ask(meta: MetaClient, *parts: str) -> str:
    request = SparkRequest(
        SPARK_CONTRIBUTOR,
        tuple(Text(p) for p in parts),
        answer_schema(),
        "compile",
        effort="high",
        max_output_tokens=MAX_OUTPUT_TOKENS,
        schema_name="rubric",
    )
    return (await meta.spark(request)).text


async def ask_phrases(meta: MetaClient, prompt: str, scope: Scope) -> Compiled:
    """One Spark call, and one repair turn when its answer fails code's checks."""
    first = await _ask(meta, prompt)
    accepted: list[CheckedPhrase] = []
    try:
        answer = parse_answer(first)
    except PhraseError as error:
        retry = await _ask(meta, prompt, first, repair_prompt([str(error)], whole=True))
        try:
            answer = parse_answer(retry)
        except PhraseError as again:
            raise CompileError(f"Spark's answer couldn't be read: {again}") from again
        return Compiled(accepted, scope.check(answer.phrases, accepted))
    failures = scope.check(answer.phrases, accepted)
    if failures:
        failures = await _repair(meta, (prompt, first), scope, accepted, failures)
    return Compiled(accepted, failures)


async def _repair(
    meta: MetaClient,
    asked: tuple[str, str],
    scope: Scope,
    accepted: list[CheckedPhrase],
    failures: list[Failure],
) -> list[Failure]:
    """The one repair turn: Spark sees its answer and the errors, and answers again for the
    failing Phrases only. Returns those still failing."""
    errors = [f"Phrase {f.answer.phrase!r}: {f.error}" for f in failures]
    reply = await _ask(meta, *asked, repair_prompt(errors, whole=False))
    try:
        repaired = parse_answer(reply).phrases[: len(failures)]
    except PhraseError:
        return failures
    return [*scope.check(repaired, accepted), *failures[len(repaired) :]]


async def compile_rubric(
    meta: MetaClient, description: str, manifest: str, settings: RubricSettings
) -> RubricDraft:
    scope = Scope(description)
    compiled = await ask_phrases(meta, compile_prompt(description, manifest), scope)
    phrases, rejected = draft_phrases(compiled, scope)
    criteria = [c for checked in compiled.accepted for c in checked.criteria]
    return RubricDraft(
        description=description,
        phrases=phrases,
        settings=settings,
        criteria=numbered(in_phrase_order(criteria, phrases)),
        rejected=rejected,
        compiled_at=datetime.now(UTC).isoformat(),
    )


def numbered(
    criteria: list[Criterion],
    taken: Collection[str] = (),
    reuse: Mapping[tuple[str, str], list[str]] | None = None,
) -> list[Criterion]:
    """Ids from the primitive, numbered from the second of a kind and never one in `taken`.
    `reuse` gives back, by (Phrase, primitive), the ids Criteria had before a recompile, so an id
    is stable while its Criterion's Phrase and primitive don't change."""
    used = set(taken)
    spare = {key: list(ids) for key, ids in (reuse or {}).items()}
    numbered: list[Criterion] = []
    for criterion in criteria:
        ids = spare.get((criterion.phrase, criterion.primitive))
        id_ = ids.pop(0) if ids else _free(criterion.primitive.replace("_", "-"), used)
        used.add(id_)
        numbered.append(criterion.model_copy(update={"id": id_}))
    return numbered


def _free(slug: str, used: set[str]) -> str:
    n = 1
    while (id_ := slug if n == 1 else f"{slug}-{n}") in used:
        n += 1
    return id_


def in_phrase_order(criteria: list[Criterion], phrases: list[DraftPhrase]) -> list[Criterion]:
    rank = {p.text: i for i, p in enumerate(sorted(phrases, key=lambda p: p.start))}
    return sorted(criteria, key=lambda c: rank[c.phrase])


def draft_phrases(
    compiled: Compiled, scope: Scope
) -> tuple[list[DraftPhrase], list[RejectedPhrase]]:
    """The Phrases compile made, in Description order: those accepted, and those still failing
    as Unsupported with the error as the reason, or rejected when they aren't in the
    Description where no other Phrase is."""
    phrases = [c.phrase for c in compiled.accepted]
    rejected: list[RejectedPhrase] = []
    for failure in compiled.failures:
        answer = failure.answer
        taken = [*scope.kept, *((p.start, p.end) for p in phrases)]
        try:
            start, end = locate(scope.description, answer.phrase, taken)
        except ValueError:
            rejected.append(RejectedPhrase(text=answer.phrase, reason=failure.error))
            continue
        phrases.append(
            DraftPhrase(
                text=answer.phrase,
                start=start,
                end=end,
                restatement=answer.restatement,
                status="unsupported",
                reason=failure.error,
            )
        )
    return sorted(phrases, key=lambda p: p.start), rejected
