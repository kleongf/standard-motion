"""What compile asks Spark for, and the code checks every answer passes before it joins a draft.

The schema is built from the catalog, so a primitive added there is one Spark can choose. Spark
says which Phrases the Description has and what each requires; code checks that each Phrase is
an exact substring that overlaps no other, and validates each Criterion against the catalog.
"""

from dataclasses import dataclass
from typing import cast, get_args

from pydantic import BaseModel, ValidationError

from winnow.criteria.models import Comparator, Criterion, CropKind, WindowKind
from winnow.criteria.primitives import PRIMITIVES
from winnow.rubric.models import DraftPhrase, PhraseStatus
from winnow.rubric.phrases import locate


class AnswerPhrase(BaseModel):
    # Spark writes an answer's keys in alphabetical order, so these names put the Phrase first,
    # then its restatement and status, and its typed Criteria last: it restates, then maps.
    phrase: str
    restatement: str
    status: PhraseStatus
    status_reason: str | None
    # Checked one by one against the catalog, so one bad Criterion fails only its Phrase.
    typed_criteria: list[dict[str, object]]


class CompileAnswer(BaseModel):
    phrases: list[AnswerPhrase]


def _nullable(kind: str) -> dict[str, object]:
    return {"type": [kind, "null"]}


def _object(properties: dict[str, object]) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def _strings() -> dict[str, object]:
    return {"type": "array", "items": {"type": "string"}}


def answer_schema() -> dict[str, object]:
    params = sorted({name for info in PRIMITIVES.values() for name in info.params})
    criterion = _object(
        {
            "primitive": {"type": "string", "enum": list(PRIMITIVES)},
            "params": _object({name: _nullable("number") for name in params}),
            "comparator": {"type": "string", "enum": list(get_args(Comparator))},
            "threshold": {"type": "number"},
            "window": _object(
                {
                    "kind": {"type": "string", "enum": list(get_args(WindowKind))},
                    "seconds": _nullable("number"),
                }
            ),
            "views": _strings(),
            "question": _nullable("string"),
            "paraphrases": _strings(),
            "crop": {"type": ["string", "null"], "enum": [*get_args(CropKind), None]},
            "hard": {"type": "boolean"},
            "assumptions": _strings(),
        }
    )
    phrase = _object(
        {
            "phrase": {"type": "string"},
            "restatement": {"type": "string"},
            "status": {"type": "string", "enum": list(get_args(PhraseStatus))},
            "status_reason": _nullable("string"),
            "typed_criteria": {"type": "array", "items": criterion},
        }
    )
    return _object({"phrases": {"type": "array", "items": phrase}})


@dataclass(frozen=True)
class CheckedPhrase:
    phrase: DraftPhrase
    criteria: list[Criterion]  # ids are placeholders until the draft numbers them


class PhraseError(ValueError):
    pass


def _validation_message(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" if e["loc"] else e["msg"]
        for e in error.errors()
    )


def _given(params: object) -> object:
    """The params a primitive takes: Spark sends every catalog param, null where unused."""
    if not isinstance(params, dict):
        return params
    return {k: v for k, v in cast(dict[str, object], params).items() if v is not None}


def _criterion(raw: dict[str, object], phrase: str, number: int) -> Criterion:
    primitive = raw.get("primitive")
    unit = next((info.unit for name, info in PRIMITIVES.items() if name == primitive), "")
    fields: dict[str, object] = {
        **raw,
        "id": f"criterion-{number}",
        "phrase": phrase,
        "params": _given(raw.get("params")),
        "unit": unit,
    }
    try:
        return Criterion.model_validate(fields)
    except ValidationError as error:
        raise PhraseError(f"Criterion {number}: {_validation_message(error)}") from error


def _status_problem(answer: AnswerPhrase) -> str | None:
    if answer.status == "checked" and not answer.typed_criteria:
        return "a checked Phrase needs at least one Criterion"
    if answer.status != "checked" and answer.typed_criteria:
        return f"a {answer.status} Phrase has no Criteria; mark it checked or drop them"
    if answer.status != "checked" and not (answer.status_reason or "").strip():
        return f"a {answer.status} Phrase needs a one-line reason"
    return None


def check_phrase(
    answer: AnswerPhrase, description: str, taken: list[tuple[int, int]]
) -> CheckedPhrase:
    """Raises PhraseError, saying what is wrong, unless the Phrase is in the Description where
    no other Phrase is and every Criterion is valid."""
    try:
        start, end = locate(description, answer.phrase, taken)
    except ValueError as error:
        raise PhraseError(str(error)) from error
    problem = _status_problem(answer)
    if problem:
        raise PhraseError(problem)
    criteria = [
        _criterion(raw, answer.phrase, i + 1) for i, raw in enumerate(answer.typed_criteria)
    ]
    reason = None if answer.status == "checked" else answer.status_reason
    phrase = DraftPhrase(
        text=answer.phrase,
        start=start,
        end=end,
        restatement=answer.restatement,
        status=answer.status,
        reason=reason,
    )
    return CheckedPhrase(phrase, criteria)


def parse_answer(text: str) -> CompileAnswer:
    """Raises PhraseError when the answer as a whole is malformed."""
    try:
        return CompileAnswer.model_validate_json(text)
    except ValidationError as error:
        raise PhraseError(f"the answer is malformed: {_validation_message(error)}") from error
